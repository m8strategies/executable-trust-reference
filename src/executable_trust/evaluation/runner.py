"""The offline evaluation harness (ET-EVAL-001, ET-EVAL-002).

Two properties make this an *independent* measurement rather than the system
grading its own homework:

**It drives the real decision path.** Every case runs through the same
:class:`~executable_trust.decisions.service.TrustService`, the same contract,
and the same decision function the request path uses. A harness that
reimplements the logic measures the reimplementation.

**Ground truth is human-authored and predates the run.** Each case states what
a correct system does and why, written before the case was executed.

The gate requires a perfect pass rate, which would be unreasonable for a
harness driving a probabilistic model and is exactly right for this one: the
verifier is deterministic and every expectation is authored, so any divergence
is a defect, not variance. The reference baseline has no variance band because
it has no variance.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from executable_trust.contracts.loader import validate_against_schema
from executable_trust.contracts.models import TrustContract
from executable_trust.contracts.registry import ContractRegistry
from executable_trust.decisions.models import GovernedResult
from executable_trust.decisions.service import TrustService
from executable_trust.decisions.store import InMemoryDecisionStore
from executable_trust.domain.enums import ActorType, Environment, Population
from executable_trust.domain.identifiers import FixedClock, SequentialIdFactory
from executable_trust.domain.models import Actor, TrustRequest
from executable_trust.evaluation.models import (
    CaseResult,
    EvaluationCase,
    SuiteSummary,
)
from executable_trust.evidence.models import EvidenceItem, EvidenceSet
from executable_trust.telemetry.recorder import TelemetryRecorder
from executable_trust.telemetry.store import InMemoryTelemetryStore
from executable_trust.verification.deterministic import (
    FaultInjectingVerifier,
    ScriptedVerifier,
)

#: Roles assigned to synthetic actors. Kept beside the golden set so a case can
#: name an actor without restating its role, and so an unknown actor is a case
#: authoring error rather than a silent denial.
SYNTHETIC_ACTOR_ROLES: dict[str, str] = {
    "avery-stone": "engineer",
    "jordan-reyes": "architect",
    "priya-natarajan": "operations",
    "sam-okafor": "auditor",
    "casey-lindqvist": "contractor",
}


@dataclass
class SuiteRun:
    """A complete evaluation run: results, summary, and provenance."""

    results: tuple[CaseResult, ...]
    summary: SuiteSummary
    provenance: dict[str, Any]

    @property
    def failures(self) -> tuple[CaseResult, ...]:
        return tuple(r for r in self.results if not r.passed)


def load_cases(path: Path | str) -> tuple[EvaluationCase, ...]:
    """Load and schema-validate the golden set from a JSONL file.

    Every case is validated against ``schemas/evaluation-case.schema.json``
    before it is typed, so a malformed case fails the run rather than quietly
    skewing it. Cases are returned sorted by identifier: a deterministic order
    is a precondition of a reproducible report.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"golden set not found: {path}")

    cases: list[EvaluationCase] = []
    seen: set[str] = set()

    with path.open(encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, start=1):
            stripped = line.strip()
            if not stripped or stripped.startswith("//"):
                continue
            try:
                raw = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path.name}:{line_no} is not valid JSON: {exc}") from exc

            validate_against_schema(
                raw, "evaluation-case.schema.json", source=f"{path.name}:{line_no}"
            )
            case = EvaluationCase.model_validate(raw)
            if case.case_id in seen:
                raise ValueError(f"{path.name}:{line_no} duplicates case id {case.case_id!r}")
            seen.add(case.case_id)
            cases.append(case)

    return tuple(sorted(cases, key=lambda c: c.case_id))


def run_case(
    case: EvaluationCase,
    registry: ContractRegistry,
    *,
    authorizer: Any,
) -> GovernedResult:
    """Execute one case through the real governed path.

    Each case gets a fresh clock, identifier factory, and stores, so cases
    cannot influence one another through shared counters. Two cases that
    interact through a shared sequence would make the report order-dependent.
    """
    clock = FixedClock()
    ids = SequentialIdFactory(seed=case.case_id)
    store = InMemoryDecisionStore()
    telemetry = InMemoryTelemetryStore()
    recorder = TelemetryRecorder(
        telemetry,
        clock=clock,
        ids=ids,
        # The harness is not production traffic and says so. Its events could
        # never be aggregated into an observed metric even if someone pointed
        # the metrics layer at them.
        environment=Environment.TEST,
        population=Population.SYNTHETIC,
    )

    verifier: Any = ScriptedVerifier(
        claims=case.claims,
        answers_question=case.answers_question,
        latency_ms=12,
    )
    if case.verifier_behavior != "normal":
        verifier = FaultInjectingVerifier(verifier, case.verifier_behavior)

    service = TrustService(
        registry,
        authorizer=authorizer,
        verifier=verifier,
        generator=_scripted_generator(case),
        store=store,
        recorder=recorder,
        clock=clock,
        ids=ids,
        environment=Environment.TEST,
        population=Population.SYNTHETIC,
    )

    role = SYNTHETIC_ACTOR_ROLES.get(case.request.actor)
    actor = Actor(
        actor_id=case.request.actor,
        actor_type=ActorType.PRINCIPAL,
        role=role or "unknown-role",
    )
    request = TrustRequest(
        correlation_id=f"corr-{case.case_id}",
        actor=actor,
        resource=case.request.resource,
        question=case.request.question,
        contract_id="executable-trust-reference",
        contract_version=case.applicable_contract_version,
    )
    evidence = EvidenceSet(
        evidence_set_ref=f"ev-{case.case_id}",
        items=tuple(
            EvidenceItem(
                evidence_id=e.evidence_id,
                text=e.text,
                relevance_score=e.relevance_score,
                provenance=e.provenance,
            )
            for e in case.evidence
        ),
    )
    return service.handle(request, evidence)


def evaluate(
    cases: tuple[EvaluationCase, ...],
    registry: ContractRegistry,
    contract: TrustContract,
    *,
    authorizer: Any,
) -> SuiteRun:
    """Run every case and compare against human-authored expectations."""
    results: list[CaseResult] = []

    for case in cases:
        result = run_case(case, registry, authorizer=authorizer)
        decision = result.decision

        divergences: list[str] = []
        if decision.outcome is not case.expected_outcome:
            divergences.append(
                f"outcome: expected {case.expected_outcome.value}, got {decision.outcome.value}"
            )
        if decision.strategy != case.expected_strategy:
            divergences.append(
                f"strategy: expected {_name(case.expected_strategy)}, "
                f"got {_name(decision.strategy)}"
            )
        if decision.reason_code != case.expected_reason_code:
            divergences.append(
                f"reason_code: expected {_name(case.expected_reason_code)}, "
                f"got {_name(decision.reason_code)}"
            )

        results.append(
            CaseResult(
                case_id=case.case_id,
                category=case.category,
                passed=not divergences,
                expected_outcome=case.expected_outcome,
                actual_outcome=decision.outcome,
                expected_strategy=case.expected_strategy,
                actual_strategy=decision.strategy,
                expected_reason_code=case.expected_reason_code,
                actual_reason_code=decision.reason_code,
                generation_invoked=result.generation_invoked,
                divergence="; ".join(divergences) or None,
            )
        )

    return SuiteRun(
        results=tuple(results),
        summary=summarize(tuple(results), contract),
        provenance=build_provenance(cases, contract),
    )


def summarize(results: tuple[CaseResult, ...], contract: TrustContract) -> SuiteSummary:
    """Aggregate results and apply the contract's baseline gate."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    minimum = _gate_minimum(contract)
    pass_rate = round(passed / total, 4) if total else 0.0

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_category.setdefault(r.category, {"total": 0, "passed": 0})
        bucket["total"] += 1
        bucket["passed"] += int(r.passed)

    return SuiteSummary(
        total=total,
        passed=passed,
        failed=total - passed,
        pass_rate=pass_rate,
        by_category=dict(sorted(by_category.items())),
        gate_minimum_pass_rate=minimum,
        # An empty suite fails the gate. A run that measured nothing has not
        # demonstrated anything, and reporting it as a pass would be the
        # emptiest possible green tick.
        gate_passed=bool(total) and pass_rate >= minimum,
    )


def build_provenance(cases: tuple[EvaluationCase, ...], contract: TrustContract) -> dict[str, Any]:
    """Metadata identifying what produced a result.

    Deliberately contains no timestamp and no git revision. Both would change
    the report on every run and make byte-identical reproducibility — the
    property this harness actually claims — impossible to check. Version
    information that matters is here; information that only records *when*
    someone ran it is not.
    """
    from executable_trust import __version__

    return {
        "label": "Reference implementation synthetic baseline",
        "package_version": __version__,
        "contract_id": contract.contract_id,
        "contract_version": contract.version,
        "ratification_status": contract.ratification.status.value,
        "case_count": len(cases),
        "verifier": "deterministic (scripted); no model provider is used",
        "evidence": "synthetic; a fictional internal-engineering corpus",
        "population": "synthetic / test — never aggregated into observed metrics",
        "note": (
            "These numbers describe this reference implementation's conformance to "
            "its own human-authored synthetic golden set. They are not a measurement "
            "of any production system and are not comparable to production figures "
            "reported in the accompanying paper."
        ),
    }


def _gate_minimum(contract: TrustContract) -> float:
    for rule in contract.evaluation:
        if rule.rule == "baseline_gate":
            value = getattr(rule, "minimum_pass_rate", None)
            if isinstance(value, int | float):
                return float(value)
    raise ValueError("contract declares no baseline gate (ET-EVAL-001)")


def _scripted_generator(case: EvaluationCase) -> Callable[[str, EvidenceSet], str]:
    """Return a generator that yields the case's candidate answer.

    A case with no candidate answer still needs a callable: if the generator is
    reached for such a case, that is itself the defect the test is looking for,
    and returning a marker string makes it visible rather than raising an
    unrelated error.
    """

    def generate(question: str, evidence: EvidenceSet) -> str:
        return case.candidate_answer or "<no candidate answer authored for this case>"

    return generate


def _name(value: Any) -> str:
    if value is None:
        return "none"
    return str(getattr(value, "value", value))
