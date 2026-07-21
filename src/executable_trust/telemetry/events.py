"""Telemetry events, and the conservative population classifier.

What is stored, and what deliberately is not:

**Stored:** outcome, strategy, reason code, evidence count, claim counts,
verification mechanism, latency, contract version, environment, population.
Facts that vary.

**Not stored:** any confidence score, any accuracy figure, any "was this
correct" field. Under a refuse-anything-imperfect rule the verification score of
every emitted answer is a constant, and a constant displayed as a score is
uninformative — which, in a product about trust, is dishonest. Correctness needs
ground truth, which only the offline harness has.

The classifier below is deliberately pessimistic: anything not explicitly marked
observed is synthetic, and an unrecognised environment resolves to the most
restrictive one. The failure it prevents is a fixture quietly counted as
production behaviour.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import (
    DecisionOutcome,
    Environment,
    EvidenceQuality,
    Population,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.models import ClaimCounts


class TelemetryEvent(BaseModel):
    """One append-only observation of a governed decision's behaviour."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    event_id: str = Field(min_length=1)
    captured_at: datetime
    decision_id: str = Field(min_length=1)
    correlation_id: str = Field(min_length=1)

    outcome: DecisionOutcome
    strategy: ResponseStrategy | None = None
    reason_code: ReasonCode | None = None

    verification_mechanism: str = Field(min_length=1)
    evidence_count: int = Field(ge=0)
    evidence_quality: EvidenceQuality | None = None
    claim_counts: ClaimCounts
    latency_ms: int = Field(ge=0)

    contract_id: str = Field(min_length=1)
    contract_version: str = Field(pattern=r"^\d+\.\d+$")

    environment: Environment
    population: Population

    @model_validator(mode="after")
    def _enforce_outcome_strategy_relation(self) -> TelemetryEvent:
        """The outcome/strategy relation holds on telemetry exactly as on decisions.

        Telemetry is where a "make the column non-null" shortcut is most
        tempting. Enforcing the relation here is what stops a third refusal
        strategy being introduced to tidy a schema.
        """
        if self.outcome is DecisionOutcome.GROUNDED:
            if self.strategy is None:
                raise ValueError("a GROUNDED telemetry event must carry a strategy")
        elif self.strategy is not None:
            raise ValueError(
                "a REFUSED telemetry event must not carry a strategy — REFUSED is an "
                "outcome, and a null strategy is the correct representation, not a gap"
            )
        elif self.reason_code is None:
            raise ValueError("a REFUSED telemetry event must carry a controlled reason code")
        return self

    @property
    def is_fault(self) -> bool:
        """True when this event records a verifier fault rather than a judgement.

        "The checker is unwell" and "the evidence did not support the claim" are
        different signals and must not share a rate. Conflating them makes a
        verifier outage look like a corpus problem.
        """
        return self.reason_code in {
            ReasonCode.VERIFIER_ERROR,
            ReasonCode.VERIFIER_TIMEOUT,
            ReasonCode.VERIFIER_OUTPUT_TRUNCATED,
            ReasonCode.MALFORMED_VERIFIER_OUTPUT,
            ReasonCode.NO_VERIFIER_AVAILABLE,
        }


def classify_environment(raw: str | None) -> Environment:
    """Resolve an environment name, failing safe.

    An unrecognised, empty, or absent value resolves to ``PRODUCTION`` — the
    most restrictive interpretation. Guessing "probably a dev box" about an
    unknown deployment is how test rows end up in a production number.
    """
    if not raw:
        return Environment.PRODUCTION
    try:
        return Environment(raw.strip().lower())
    except ValueError:
        return Environment.PRODUCTION


def classify_population(raw: str | None) -> Population:
    """Resolve a population, failing safe.

    Only the exact string ``observed`` yields ``OBSERVED``. Everything else —
    unknown values, empty strings, absent values — is ``SYNTHETIC``, because
    the cost of miscounting generated activity as real is higher than the cost
    of the reverse.
    """
    if raw and raw.strip().lower() == Population.OBSERVED.value:
        return Population.OBSERVED
    return Population.SYNTHETIC
