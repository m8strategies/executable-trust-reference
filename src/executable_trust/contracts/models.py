"""Typed view of a versioned trust contract.

The YAML file is the artifact a human reviews and ratifies. These models are
how the runtime reads it. Both are the same contract; neither is a copy of the
other's intent.

Only the parts the runtime actually enforces are modelled with types. The full
document is kept in :attr:`TrustContract.raw` so the traceability validator can
walk every declared rule identifier, including those in sections the runtime
does not read. That split is deliberate: a rule the code does not consume still
has to be tested, and dropping it from the typed view would hide it.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from executable_trust.domain.enums import (
    ClaimVerdict,
    DecisionOutcome,
    LifecycleState,
    RatificationStatus,
    ResponseStrategy,
)


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Ratification(_Frozen):
    """Whether, when, and by whom this contract version was ratified."""

    status: RatificationStatus
    ratified_on: date
    ratified_by: str = Field(min_length=1)
    effective_from: datetime
    amendments: tuple[str, ...] = ()


class Rule(_Frozen):
    """One executable rule with a stable identifier.

    ``extra="allow"`` here, uniquely in this module: individual rules carry
    rule-specific parameters (a threshold, a minimum sample) that vary by rule
    and would otherwise need a model per rule for no benefit. The identifier,
    name, and statement are always required.
    """

    model_config = ConfigDict(frozen=True, extra="allow")

    id: str = Field(pattern=r"^ET-[A-Z]+-\d{3}$")
    rule: str = Field(min_length=1)
    statement: str = Field(min_length=1)
    reason_code: str | None = None


class Vocabulary(_Frozen):
    """The controlled vocabulary this contract version declares.

    Validated against the implementation's enums at load time. A contract
    declaring a strategy the code does not implement, or omitting one it does,
    fails closed rather than being partially honoured.
    """

    claim_verdicts: tuple[ClaimVerdict, ...]
    decision_outcomes: tuple[DecisionOutcome, ...]
    response_strategies: tuple[ResponseStrategy, ...]
    outcome_strategy_relation: tuple[Rule, ...]


class EvidenceGate(_Frozen):
    """Thresholds a retrieved evidence set must clear before generation runs."""

    id: str
    min_similarity_score: float = Field(ge=0.0, le=1.0)
    min_chunks_required: int = Field(ge=1)
    top_k: int = Field(ge=1)
    statement: str
    refusal_reason_code: str


class EvidenceProvenanceRule(_Frozen):
    """Which evidence origins are acceptable."""

    id: str
    required: bool
    permitted_sources: tuple[str, ...]
    statement: str
    refusal_reason_code: str


class EvidenceSection(_Frozen):
    gate: EvidenceGate
    provenance: EvidenceProvenanceRule
    quality_labels: tuple[str, ...]


class VerificationBudget(_Frozen):
    call_budget_ms_p50: int = Field(ge=1)


class VerificationSection(_Frozen):
    """Verification rules, in the order the decision function evaluates them.

    ``fail_closed`` is structurally constant: a contract that declares
    otherwise is not an Executable Trust contract, and the schema refuses to
    load it.
    """

    fail_closed: bool
    required_claim_fields: tuple[str, ...]
    statement_on_missing_fields: str
    rules: tuple[Rule, ...]
    budget: VerificationBudget


class TelemetryPopulations(_Frozen):
    """Which populations exist, and which may be aggregated as observed."""

    environments: tuple[str, ...]
    classifications: tuple[str, ...]
    observed_metric_environments: tuple[str, ...]


class TelemetrySection(_Frozen):
    rules: tuple[Rule, ...]
    populations: TelemetryPopulations


class LifecycleTransitionRule(_Frozen):
    """One declared transition and the attribution it requires."""

    id: str
    from_: LifecycleState = Field(alias="from")
    to: LifecycleState
    requires_human_review: bool
    requires_actor: bool
    requires_role: bool
    requires_reason_code: bool
    requires_successor: bool = False
    statement: str

    model_config = ConfigDict(frozen=True, extra="forbid", populate_by_name=True)


class LifecycleSection(_Frozen):
    states: tuple[LifecycleState, ...]
    initial_state: LifecycleState
    terminal_states: tuple[LifecycleState, ...]
    transitions: tuple[LifecycleTransitionRule, ...]
    rules: tuple[Rule, ...]


class TrustContract(_Frozen):
    """A loaded, schema-valid trust contract.

    Being loaded does not make it governing. :meth:`require_ratified` is the
    gate, and it is called by the resolver rather than by every consumer, so a
    caller cannot forget it.
    """

    contract_id: str
    version: str = Field(pattern=r"^\d+\.\d+$")
    title: str
    ratification: Ratification
    vocabulary: Vocabulary
    evidence: EvidenceSection
    verification: VerificationSection
    authorization: tuple[Rule, ...]
    contract_resolution: tuple[Rule, ...]
    telemetry: TelemetrySection
    metrics: tuple[Rule, ...]
    resilience: tuple[Rule, ...]
    lifecycle: LifecycleSection
    evaluation: tuple[Rule, ...]

    #: The document exactly as parsed, for the traceability validator.
    raw: dict[str, Any] = Field(default_factory=dict, repr=False)

    @property
    def key(self) -> tuple[str, str]:
        """Registry key: identifier and version together."""
        return (self.contract_id, self.version)

    @property
    def is_ratified(self) -> bool:
        return self.ratification.status is RatificationStatus.RATIFIED

    def rule(self, rule_id: str) -> Rule | None:
        """Return the rule with ``rule_id``, or ``None``."""
        return self.all_rules().get(rule_id)

    def all_rules(self) -> dict[str, Rule]:
        """Every rule declared anywhere in the contract, keyed by identifier."""
        collected: dict[str, Rule] = {}
        groups: tuple[tuple[Rule, ...], ...] = (
            self.vocabulary.outcome_strategy_relation,
            self.verification.rules,
            self.authorization,
            self.contract_resolution,
            self.telemetry.rules,
            self.metrics,
            self.resilience,
            self.lifecycle.rules,
            self.evaluation,
        )
        for group in groups:
            for r in group:
                collected[r.id] = r
        return collected

    def all_rule_ids(self) -> frozenset[str]:
        """Identifiers of every rule, including those carried on structured sections.

        The evidence gate, the provenance rule, and each lifecycle transition
        carry identifiers on their own models rather than as free-standing
        rules. They are included here because a rule's obligation to be tested
        does not depend on where it happens to sit in the document.
        """
        ids = set(self.all_rules())
        ids.add(self.evidence.gate.id)
        ids.add(self.evidence.provenance.id)
        ids.update(t.id for t in self.lifecycle.transitions)
        return frozenset(ids)

    def minimum_sample(self) -> int:
        """Sample size below which a rate is withheld.

        Read from the contract rather than hardcoded, so the people accountable
        for the threshold can see and change the number without a code change.
        """
        for r in self.metrics:
            if r.rule == "rates_withheld_below_minimum_sample":
                value = getattr(r, "minimum_sample", None)
                if isinstance(value, int):
                    return value
        raise ValueError("contract declares no minimum_sample for rate withholding")

    def transition_rule(
        self, from_state: LifecycleState, to_state: LifecycleState
    ) -> LifecycleTransitionRule | None:
        """Return the declared transition, or ``None`` if undeclared."""
        for t in self.lifecycle.transitions:
            if t.from_ is from_state and t.to is to_state:
                return t
        return None
