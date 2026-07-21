"""Cross-artifact consistency checks.

Schema validation proves each artifact is well formed on its own. These checks
prove the artifacts agree *with each other* — which is where the real defects
live, because every author is best positioned to see their own piece and worst
positioned to see where it stops lining up with the next one.

Used by ``scripts/validate_contracts.py`` and by the contract test suite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from executable_trust.contracts.registry import ContractRegistry
from executable_trust.domain.enums import (
    LIFECYCLE_REASON_CODES,
    DecisionOutcome,
    LifecycleState,
    ReasonCode,
)


@dataclass
class ValidationReport:
    """Accumulated findings. Empty ``errors`` means the artifact set is coherent."""

    errors: list[str] = field(default_factory=list)
    checks_run: int = 0

    @property
    def ok(self) -> bool:
        return not self.errors

    def check(self, condition: bool, message: str) -> None:
        self.checks_run += 1
        if not condition:
            self.errors.append(message)

    def merge(self, other: ValidationReport) -> None:
        self.errors.extend(other.errors)
        self.checks_run += other.checks_run


def validate_reason_code_coverage(registry: ContractRegistry) -> ValidationReport:
    """Every declared reason code names a rule that exists in some contract."""
    report = ValidationReport()
    known_rules: set[str] = set()
    for contract_id in {cid for cid, _ in _keys(registry)}:
        for version in registry.versions(contract_id):
            known_rules |= registry.get(contract_id, version).all_rule_ids()

    for code, entry in registry.reason_codes.items():
        rule_id = str(entry.get("rule_id", ""))
        report.check(
            rule_id in known_rules,
            f"reason code {code!r} names rule id {rule_id!r}, which no contract declares",
        )
        origin = entry.get("origin")
        report.check(
            origin in {"paper", "derived"},
            f"reason code {code!r} declares origin {origin!r}; expected 'paper' or 'derived'",
        )
    return report


def validate_outcome_applicability(registry: ContractRegistry) -> ValidationReport:
    """Non-lifecycle reason codes declare the outcome they explain.

    Every verification reason code explains a refusal. A code that claims to
    apply to ``GROUNDED`` would mean a grounded answer needed excusing, which
    is a category error.
    """
    report = ValidationReport()
    lifecycle_values = {c.value for c in LIFECYCLE_REASON_CODES}

    for code, entry in registry.reason_codes.items():
        if code in lifecycle_values:
            report.check(
                "applies_to_outcome" not in entry,
                f"lifecycle reason code {code!r} must not declare applies_to_outcome; "
                "it explains a transition, not a verification outcome",
            )
            continue
        applies = entry.get("applies_to_outcome")
        report.check(
            applies == DecisionOutcome.REFUSED.value,
            f"reason code {code!r} declares applies_to_outcome={applies!r}; "
            "every verification reason code explains a refusal",
        )
    return report


def validate_rule_reason_code_links(registry: ContractRegistry) -> ValidationReport:
    """Every ``reason_code`` referenced by a rule is in the controlled set."""
    report = ValidationReport()
    controlled = set(registry.reason_codes)

    for contract_id, version in _keys(registry):
        contract = registry.get(contract_id, version)
        referenced: set[str] = {
            r.reason_code for r in contract.all_rules().values() if r.reason_code
        }
        referenced.add(contract.evidence.gate.refusal_reason_code)
        referenced.add(contract.evidence.provenance.refusal_reason_code)

        for code in sorted(referenced):
            report.check(
                code in controlled,
                f"{contract_id} v{version} references uncontrolled reason code {code!r}",
            )
    return report


def validate_lifecycle_coherence(registry: ContractRegistry) -> ValidationReport:
    """The declared transition set is internally consistent.

    Checks that terminal states have no outbound transitions, that every state
    except the initial one is reachable, and that supersession names a
    successor. A lifecycle with an unreachable state is a lifecycle with a
    typo.
    """
    report = ValidationReport()

    for contract_id, version in _keys(registry):
        lc = registry.get(contract_id, version).lifecycle
        label = f"{contract_id} v{version}"

        for terminal in lc.terminal_states:
            outbound = [t for t in lc.transitions if t.from_ is terminal]
            report.check(
                not outbound,
                f"{label}: terminal state {terminal.value} declares outbound "
                f"transitions {[t.id for t in outbound]}; terminal means permanent",
            )

        reachable = {lc.initial_state} | {t.to for t in lc.transitions}
        for state in lc.states:
            report.check(
                state in reachable,
                f"{label}: state {state.value} is declared but unreachable",
            )

        for t in lc.transitions:
            if t.to is LifecycleState.SUPERSEDED:
                report.check(
                    t.requires_successor,
                    f"{label}: transition {t.id} targets SUPERSEDED but does not "
                    "require a successor reference",
                )
            if t.to in {LifecycleState.ACCEPTED, LifecycleState.REJECTED}:
                report.check(
                    t.requires_human_review and t.requires_actor and t.requires_role,
                    f"{label}: transition {t.id} reaches {t.to.value} without "
                    "requiring an attributable accountable human review",
                )
    return report


def validate_outcome_strategy_relation(registry: ContractRegistry) -> ValidationReport:
    """The contract declares exactly two strategies and the three relation rules.

    Pinned explicitly because the temptation to add a third ``REFUSAL``
    strategy — so that a telemetry column is never null — is real and
    recurring. It would duplicate the outcome across two axes.
    """
    report = ValidationReport()
    required_rules = {
        "outcome_grounded_requires_strategy",
        "outcome_refused_forbids_strategy",
        "outcome_refused_requires_reason_code",
    }

    for contract_id, version in _keys(registry):
        vocab = registry.get(contract_id, version).vocabulary
        label = f"{contract_id} v{version}"
        strategies = {s.value for s in vocab.response_strategies}
        report.check(
            strategies == {"DIRECT", "BOUNDED"},
            f"{label}: response_strategies is {sorted(strategies)}; expected exactly "
            "['BOUNDED', 'DIRECT'] — REFUSED is an outcome, never a strategy",
        )
        declared = {r.rule for r in vocab.outcome_strategy_relation}
        missing = required_rules - declared
        report.check(
            not missing,
            f"{label}: outcome_strategy_relation omits {sorted(missing)}",
        )
    return report


def validate_enum_alignment(registry: ContractRegistry) -> ValidationReport:
    """The controlled reason-code set matches the implementation's enum exactly."""
    report = ValidationReport()
    declared = set(registry.reason_codes)
    implemented = {c.value for c in ReasonCode}
    report.check(
        declared == implemented,
        "reason-code set and ReasonCode enum disagree: "
        f"only-in-contract={sorted(declared - implemented)}, "
        f"only-in-code={sorted(implemented - declared)}",
    )
    return report


def validate_amendments(registry: ContractRegistry) -> ValidationReport:
    """Amendments preserve their prior version and cite roles distinctly."""
    report = ValidationReport()
    for amendment_id, amendment in registry.amendments.items():
        report.check(
            amendment.get("preserves_prior_version") is True,
            f"amendment {amendment_id} does not assert preserves_prior_version",
        )
        report.check(
            amendment.get("author") != amendment.get("ratifier"),
            f"amendment {amendment_id} names the same party as author and ratifier; "
            "authorship is not ratification",
        )
        prev = str(amendment["previous_contract_version"])
        new = str(amendment["new_contract_version"])
        report.check(
            _version_key(new) > _version_key(prev),
            f"amendment {amendment_id} moves from v{prev} to v{new}, which is not forward",
        )
    return report


def validate_registry(registry: ContractRegistry) -> ValidationReport:
    """Run every cross-artifact check and return the combined report."""
    report = ValidationReport()
    for check in (
        validate_enum_alignment,
        validate_reason_code_coverage,
        validate_outcome_applicability,
        validate_rule_reason_code_links,
        validate_lifecycle_coherence,
        validate_outcome_strategy_relation,
        validate_amendments,
    ):
        report.merge(check(registry))
    return report


def _keys(registry: ContractRegistry) -> list[tuple[str, str]]:
    """Every registered ``(contract_id, version)`` pair, sorted."""
    return registry.registered()


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))
