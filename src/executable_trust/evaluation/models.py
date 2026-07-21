"""Evaluation case and result models.

Layer 3. The offline harness answers a question runtime enforcement cannot:
*are the rules working?* Runtime enforcement grades its own output; only a
harness with human-authored ground truth can say whether a decision was
correct.

Every case here is synthetic and every expected outcome was written by a human
before the case was run. That ordering is what makes it ground truth rather
than a recording of current behaviour — a baseline captured from what the code
already does measures nothing.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import DecisionOutcome, ReasonCode, ResponseStrategy


class CaseRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    actor: str = Field(min_length=1)
    resource: str = Field(min_length=1)
    question: str = Field(min_length=1)


class CaseEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    provenance: str


class EvaluationCase(BaseModel):
    """One human-authored golden case. Synthetic by construction."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str = Field(pattern=r"^\d{2}-[a-z0-9-]+$")
    category: str = Field(min_length=1)
    synthetic: bool

    request: CaseRequest
    evidence: tuple[CaseEvidence, ...] = ()
    candidate_answer: str | None = None
    claims: tuple[Mapping[str, Any], ...] = ()
    verifier_behavior: str = "normal"
    answers_question: bool | None = True

    applicable_contract_version: str = Field(min_length=1)

    expected_outcome: DecisionOutcome
    expected_strategy: ResponseStrategy | None = None
    expected_reason_code: ReasonCode | None = None

    rationale: str = Field(min_length=1)

    @model_validator(mode="after")
    def _case_is_synthetic(self) -> EvaluationCase:
        if not self.synthetic:
            raise ValueError(
                f"case {self.case_id} is not marked synthetic; every case in this "
                "repository is synthetic and the flag exists to make that checkable"
            )
        return self

    @model_validator(mode="after")
    def _expectations_obey_the_outcome_relation(self) -> EvaluationCase:
        """A malformed expectation cannot enter the golden set.

        Without this, a case could expect a refusal *with* a strategy — and
        since the implementation can never produce one, the case would fail
        forever for a reason that has nothing to do with the code.
        """
        if self.expected_outcome is DecisionOutcome.GROUNDED:
            if self.expected_strategy is None:
                raise ValueError(f"case {self.case_id}: a GROUNDED expectation needs a strategy")
            if self.expected_reason_code is not None:
                raise ValueError(
                    f"case {self.case_id}: a GROUNDED expectation must not name a reason code"
                )
        else:
            if self.expected_strategy is not None:
                raise ValueError(
                    f"case {self.case_id}: a REFUSED expectation must not name a strategy"
                )
            if self.expected_reason_code is None:
                raise ValueError(f"case {self.case_id}: a REFUSED expectation needs a reason code")
        return self


class CaseResult(BaseModel):
    """What the system actually did, beside what a human said it should do."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    case_id: str
    category: str
    passed: bool

    expected_outcome: DecisionOutcome
    actual_outcome: DecisionOutcome
    expected_strategy: ResponseStrategy | None
    actual_strategy: ResponseStrategy | None
    expected_reason_code: ReasonCode | None
    actual_reason_code: ReasonCode | None

    generation_invoked: bool
    divergence: str | None = None

    @property
    def outcome_matched(self) -> bool:
        return self.expected_outcome is self.actual_outcome


class SuiteSummary(BaseModel):
    """Aggregate results.

    Note what is absent: there is no accuracy figure here that could be quoted
    beside a runtime telemetry rate. This summary describes *the reference
    implementation's conformance to its own golden set*, nothing more.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int
    passed: int
    failed: int
    pass_rate: float
    by_category: dict[str, dict[str, int]]
    gate_minimum_pass_rate: float
    gate_passed: bool
