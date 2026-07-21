"""The immutable decision record.

One record per governed decision. It carries everything needed to explain that
decision after the fact without re-running anything: which contract governed it,
what the authorization result was, what the verifier decided, how much evidence
there was, and how long the check took.

Immutability is enforced three ways, because one way is a convention:

1. the model is frozen, so attribute assignment raises;
2. the store refuses to overwrite an existing identifier;
3. corrections go through :meth:`DecisionRecord.superseded_by`, which creates a
   *new* record and never touches the original.

There is deliberately no ``lifecycle_state`` field. State is derived from the
append-only transition log; a stored current-state field would be a second
source of truth that can disagree with the log.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import (
    AuthorizationResult,
    DecisionOutcome,
    Environment,
    Population,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.models import ClaimCounts


class DecisionRecord(BaseModel):
    """An immutable record of one governed decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    decision_id: str = Field(min_length=1)
    recorded_at: datetime

    # -- governing contract ------------------------------------------------
    contract_id: str = Field(min_length=1)
    contract_version: str = Field(pattern=r"^\d+\.\d+$")
    amendment_ref: str | None = None

    # -- request identity --------------------------------------------------
    correlation_id: str = Field(min_length=1)
    subject_id: str = Field(min_length=1)
    request_ref: str = Field(min_length=1)
    evidence_set_ref: str = Field(min_length=1)

    # -- what was decided --------------------------------------------------
    authorization_result: AuthorizationResult
    outcome: DecisionOutcome
    strategy: ResponseStrategy | None = None
    reason_code: ReasonCode | None = None

    # -- how it was decided ------------------------------------------------
    verification_mechanism: str = Field(min_length=1)
    evidence_count: int = Field(ge=0)
    claim_counts: ClaimCounts
    latency_ms: int = Field(ge=0)

    # -- provenance --------------------------------------------------------
    population: Population
    environment: Environment

    # -- supersession ------------------------------------------------------
    supersedes: str | None = None

    @model_validator(mode="after")
    def _enforce_outcome_strategy_relation(self) -> DecisionRecord:
        """The same relation the verification decision enforces (ET-OUT-001..003).

        Re-checked here rather than trusted from upstream: a record can be
        reconstructed from storage or built by a test, and an invariant that
        holds only on the happy path is not an invariant.
        """
        if self.outcome is DecisionOutcome.GROUNDED:
            if self.strategy is None:
                raise ValueError("a GROUNDED decision record must carry a strategy (ET-OUT-001)")
            if self.reason_code is not None:
                raise ValueError("a GROUNDED decision record must not carry a refusal reason code")
        else:
            if self.strategy is not None:
                raise ValueError("a REFUSED decision record must not carry a strategy (ET-OUT-002)")
            if self.reason_code is None:
                raise ValueError(
                    "a REFUSED decision record must carry a controlled reason code (ET-OUT-003)"
                )
        return self

    @model_validator(mode="after")
    def _denied_requests_never_reach_verification(self) -> DecisionRecord:
        """A denied request cannot carry evidence or claim counts.

        Authorization precedes retrieval. A record showing both a denial and
        retrieved evidence would mean the gate ran out of order, which is a
        defect worth catching at the boundary rather than discovering in an
        audit.
        """
        if self.authorization_result is AuthorizationResult.DENIED:
            if self.outcome is not DecisionOutcome.REFUSED:
                raise ValueError("an authorization denial must produce a REFUSED outcome")
            if self.evidence_count != 0:
                raise ValueError(
                    "an authorization denial must record zero evidence: authorization "
                    "precedes retrieval, so no evidence was read"
                )
            if self.claim_counts.measured:
                raise ValueError(
                    "an authorization denial must record unmeasured claim counts: "
                    "verification never ran"
                )
        return self

    def superseded_by(
        self,
        *,
        decision_id: str,
        recorded_at: datetime,
        outcome: DecisionOutcome,
        strategy: ResponseStrategy | None,
        reason_code: ReasonCode | None,
        verification_mechanism: str,
        claim_counts: ClaimCounts,
        evidence_count: int,
        latency_ms: int,
    ) -> DecisionRecord:
        """Build a successor record that cites this one.

        The successor references the predecessor. The predecessor is returned
        unchanged and is never edited — supersession is recorded *by* the
        successor and by a lifecycle transition, never *onto* the original.
        """
        return DecisionRecord(
            decision_id=decision_id,
            recorded_at=recorded_at,
            contract_id=self.contract_id,
            contract_version=self.contract_version,
            amendment_ref=self.amendment_ref,
            correlation_id=self.correlation_id,
            subject_id=self.subject_id,
            request_ref=self.request_ref,
            evidence_set_ref=self.evidence_set_ref,
            authorization_result=self.authorization_result,
            outcome=outcome,
            strategy=strategy,
            reason_code=reason_code,
            verification_mechanism=verification_mechanism,
            evidence_count=evidence_count,
            claim_counts=claim_counts,
            latency_ms=latency_ms,
            population=self.population,
            environment=self.environment,
            supersedes=self.decision_id,
        )
