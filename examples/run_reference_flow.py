#!/usr/bin/env python3
"""Walk the governed request path, one scenario at a time.

    python examples/run_reference_flow.py

Runs a grounded request and each refusal path, then demonstrates the lifecycle
and the fail-open telemetry guarantee. No credentials, no network, no database.

SYNTHETIC: every actor, resource, document, and passage below is fictional.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from executable_trust.authorization import DeterministicAuthorizer  # noqa: E402
from executable_trust.contracts import build_default_registry  # noqa: E402
from executable_trust.decisions import InMemoryDecisionStore, TrustService  # noqa: E402
from executable_trust.domain.enums import (  # noqa: E402
    ActorType,
    Environment,
    Population,
)
from executable_trust.domain.identifiers import FixedClock, SequentialIdFactory  # noqa: E402
from executable_trust.domain.models import Actor, TrustRequest  # noqa: E402
from executable_trust.evidence import EvidenceItem, EvidenceSet  # noqa: E402
from executable_trust.lifecycle import InMemoryTransitionLog, LifecycleStateMachine  # noqa: E402
from executable_trust.telemetry import (  # noqa: E402
    AlwaysFailingTelemetryStore,
    InMemoryTelemetryStore,
    TelemetryRecorder,
    compute_behavior_metrics,
)
from executable_trust.verification import ScriptedVerifier  # noqa: E402

CONTRACT_ID = "executable-trust-reference"
QUESTION = "How long does an approved code review stay valid?"
ANSWER = "An approved code review remains valid for 14 calendar days."

ENGINEER = Actor(actor_id="avery-stone", actor_type=ActorType.PRINCIPAL, role="engineer")
ARCHITECT = Actor(actor_id="jordan-reyes", actor_type=ActorType.PRINCIPAL, role="architect")
CONTRACTOR = Actor(actor_id="casey-lindqvist", actor_type=ActorType.PRINCIPAL, role="contractor")

SUPPORTED = ({"text": ANSWER.rstrip("."), "verdict": "SUPPORTED", "evidence_ref": "hb-cr-004"},)
PARTLY_SUPPORTED = (
    *SUPPORTED,
    {"text": "Reviews are also escalated to the architecture group", "verdict": "UNSUPPORTED"},
)


def _evidence(score: float = 0.9, provenance: str = "governed_corpus") -> EvidenceSet:
    return EvidenceSet(
        evidence_set_ref="ev-example",
        items=(
            EvidenceItem(
                evidence_id="hb-cr-004",
                text="An approved code review remains valid for 14 calendar days.",
                relevance_score=score,
                provenance=provenance,
            ),
        ),
    )


class CountingGenerator:
    """Records whether it was called, so pre-generation refusals are provable."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, question: str, evidence: EvidenceSet) -> str:
        self.calls += 1
        return ANSWER


def _describe(label: str, result, generator: CountingGenerator) -> None:
    d = result.decision
    verdict = f"{d.outcome.value}/{d.strategy.value}" if d.strategy else d.outcome.value
    code = d.reason_code.value if d.reason_code else "-"
    print(
        f"  {label:<34} {verdict:<20} {code:<32} "
        f"generator invoked: {'yes' if generator.calls else 'no'}"
    )


def main() -> int:
    registry = build_default_registry()
    telemetry = InMemoryTelemetryStore()

    print("=" * 108)
    print("EXECUTABLE TRUST — REFERENCE FLOW   (all data synthetic)")
    print("=" * 108)
    print(f"\n  {'scenario':<34} {'outcome':<20} {'reason code':<32} generation")
    print("  " + "-" * 104)

    scenarios = [
        ("grounded, direct", ENGINEER, _evidence(), SUPPORTED, "1.0"),
        ("insufficient evidence", ENGINEER, _evidence(score=0.20), SUPPORTED, "1.0"),
        ("empty retrieval", ENGINEER, EvidenceSet(evidence_set_ref="ev-empty"), SUPPORTED, "1.0"),
        (
            "invalid evidence provenance",
            ENGINEER,
            _evidence(score=0.99, provenance="unverified_scrape"),
            SUPPORTED,
            "1.0",
        ),
        ("authorization denied", CONTRACTOR, _evidence(), SUPPORTED, "1.0"),
        ("partially supported answer", ENGINEER, _evidence(), PARTLY_SUPPORTED, "1.0"),
        ("empty claim set", ENGINEER, _evidence(), (), "1.0"),
        ("unratified (draft) contract", ENGINEER, _evidence(), SUPPORTED, "0.9"),
        ("unknown contract version", ENGINEER, _evidence(), SUPPORTED, "9.9"),
    ]

    for label, actor, evidence, claims, version in scenarios:
        clock, ids = FixedClock(), SequentialIdFactory(seed=label.replace(" ", "-"))
        generator = CountingGenerator()
        service = TrustService(
            registry,
            authorizer=DeterministicAuthorizer(),
            verifier=ScriptedVerifier(claims=claims),
            generator=generator,
            store=InMemoryDecisionStore(),
            recorder=TelemetryRecorder(
                telemetry,
                clock=clock,
                ids=ids,
                environment=Environment.PRODUCTION,
                population=Population.OBSERVED,
            ),
            clock=clock,
            ids=ids,
        )
        request = TrustRequest(
            correlation_id=f"corr-{label.replace(' ', '-')}",
            actor=actor,
            resource="handbook/code-review",
            question=QUESTION,
            contract_id=CONTRACT_ID,
            contract_version=version,
        )
        _describe(label, service.handle(request, evidence), generator)

    # -- Lifecycle ---------------------------------------------------------
    print("\n" + "=" * 108)
    print("LIFECYCLE — current state is derived from an append-only log")
    print("=" * 108)

    contract = registry.resolve(CONTRACT_ID, "1.0")
    log = InMemoryTransitionLog()
    machine = LifecycleStateMachine(
        contract, log, clock=FixedClock(), ids=SequentialIdFactory(seed="lc")
    )

    print(f"\n  initial state (no transitions):  {machine.current_state('dec-1').value}")
    machine.accept("dec-1", reviewer=ARCHITECT, note="approved at architecture review")
    print(f"  after accountable acceptance:    {machine.current_state('dec-1').value}")
    machine.supersede("dec-1", successor_decision_id="dec-2", actor=ARCHITECT)
    print(f"  after supersession:              {machine.current_state('dec-1').value}")

    print("\n  transition log (the authority):")
    for t in machine.history("dec-1"):
        successor = f" -> {t.successor_decision_id}" if t.successor_decision_id else ""
        print(
            f"    #{t.sequence}  {t.from_state.value!s:<10} -> {t.to_state.value:<11}"
            f" by {t.actor.actor_id} ({t.actor.role})  {t.reason_code.value}{successor}"
        )

    try:
        machine.accept("dec-1", reviewer=ARCHITECT)
    except Exception as exc:
        print(f"\n  re-accepting a terminal record is refused:\n    {type(exc).__name__}: {exc}")

    try:
        machine.accept("dec-9", reviewer=Actor(actor_id="cron", actor_type=ActorType.SYSTEM))
    except Exception as exc:
        print(f"\n  a system actor cannot accept:\n    {type(exc).__name__}: {exc}")

    # -- Telemetry ---------------------------------------------------------
    print("\n" + "=" * 108)
    print("TELEMETRY AND METRICS")
    print("=" * 108)

    metrics = compute_behavior_metrics(telemetry.all(), contract)
    print(f"\n  decisions in window:        {metrics.total}")
    print(f"  counts:                     {metrics.counts}")
    print(f"  minimum sample:             {metrics.minimum_sample}")
    print(f"  insufficient sample:        {metrics.insufficient_sample}")
    print(f"  grounded rate:              {metrics.grounded_rate}   <- withheld, not zero")
    print(f"  reason codes:               {metrics.reason_code_counts}")
    print(f"\n  quality note shipped with the payload:\n    {metrics.quality_note}")

    # Fail-open capture: the decision is unchanged when the backend is dead.
    clock, ids = FixedClock(), SequentialIdFactory(seed="failopen")
    generator = CountingGenerator()
    broken = TrustService(
        registry,
        authorizer=DeterministicAuthorizer(),
        verifier=ScriptedVerifier(claims=SUPPORTED),
        generator=generator,
        store=InMemoryDecisionStore(),
        recorder=TelemetryRecorder(
            AlwaysFailingTelemetryStore(),
            clock=clock,
            ids=ids,
            environment=Environment.PRODUCTION,
            population=Population.OBSERVED,
        ),
        clock=clock,
        ids=ids,
    )
    result = broken.handle(
        TrustRequest(
            correlation_id="corr-failopen",
            actor=ENGINEER,
            resource="handbook/code-review",
            question=QUESTION,
            contract_id=CONTRACT_ID,
            contract_version="1.0",
        ),
        _evidence(),
    )
    print("\n  with a dead telemetry backend:")
    print(f"    telemetry captured:       {result.telemetry_captured}")
    print(
        f"    governed outcome:         {result.decision.outcome.value}"
        f"/{result.decision.strategy.value}   <- unchanged"
    )

    print("\n" + "=" * 108)
    print("Enforcement fails closed. Telemetry fails open. Reversing either is a defect.")
    print("=" * 108)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
