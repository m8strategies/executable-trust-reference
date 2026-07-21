"""Verification models and the parsing that fails closed.

Two shapes live here and the boundary between them is the point.

:class:`VerifierResponse` is what a verification mechanism returns: loosely
typed, possibly malformed, not yet trusted. Its ``claims`` are raw mappings
because a real verifier returns whatever it returns, and pretending otherwise
would hide the parsing step where the fail-closed guarantees actually live.

:class:`VerificationDecision` is what the decision function produces: fully
typed, with the outcome/strategy relation enforced structurally. It cannot be
constructed in an inconsistent state.

:func:`parse_claims` is the crossing. It distinguishes a missing verdict from an
unknown one from a malformed claim, because those are three different defects
and telemetry that merges them cannot tell you which verifier is misbehaving.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import (
    ClaimVerdict,
    DecisionOutcome,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.errors import VerifierFailure
from executable_trust.domain.models import Claim, ClaimCounts


class VerifierResponse(BaseModel):
    """Raw output from a verification mechanism, before it is trusted.

    ``answers_question`` is ``bool | None`` and has **no default of True**. A
    verifier that omits the field has produced malformed output, and the
    decision function refuses. Defaulting it to ``True`` would mean a verifier
    that silently stopped emitting the field would start promoting every answer
    — the exact fail-open shape this architecture exists to prevent.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    mechanism: str = Field(min_length=1)
    claims: tuple[Mapping[str, Any], ...] = ()
    answers_question: bool | None = None
    truncated: bool = False
    latency_ms: int = Field(default=0, ge=0)


class VerificationDecision(BaseModel):
    """The governed outcome of one verification pass.

    The outcome/strategy relation is enforced here, in the type, so an
    inconsistent decision cannot be constructed anywhere in the system:

    - ``GROUNDED`` requires a strategy of ``DIRECT`` or ``BOUNDED``;
    - ``REFUSED`` forbids a strategy and requires a controlled reason code.

    ``REFUSED`` is not also a strategy. Modelling it in both places would put
    one fact on two axes that could then disagree, and the null strategy on a
    refusal is not a gap to be filled — it is the correct representation of
    "no answer was presented, so there was no way to present it".
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: DecisionOutcome
    strategy: ResponseStrategy | None = None
    reason_code: ReasonCode | None = None
    claims: tuple[Claim, ...] = ()
    claim_counts: ClaimCounts = Field(default_factory=ClaimCounts.not_measured)
    mechanism: str = Field(min_length=1)
    latency_ms: int = Field(default=0, ge=0)
    detail: str = ""

    @model_validator(mode="after")
    def _enforce_outcome_strategy_relation(self) -> VerificationDecision:
        if self.outcome is DecisionOutcome.GROUNDED:
            if self.strategy is None:
                raise ValueError("a GROUNDED decision must carry a response strategy (ET-OUT-001)")
            if self.reason_code is not None:
                raise ValueError(
                    "a GROUNDED decision must not carry a refusal reason code; "
                    "reason codes explain refusals (ET-OUT-003)"
                )
        else:
            if self.strategy is not None:
                raise ValueError(
                    "a REFUSED decision must not carry a response strategy — "
                    "REFUSED is an outcome, not a strategy (ET-OUT-002)"
                )
            if self.reason_code is None:
                raise ValueError(
                    "a REFUSED decision must carry a controlled reason code (ET-OUT-003)"
                )
        return self

    @property
    def grounded(self) -> bool:
        """Derived, never stored.

        A convenience predicate is fine; a persisted boolean beside the outcome
        is not, because the two can drift and then one field means two things.
        """
        return self.outcome is DecisionOutcome.GROUNDED

    @classmethod
    def refuse(
        cls,
        reason_code: ReasonCode,
        *,
        mechanism: str,
        detail: str = "",
        claims: tuple[Claim, ...] = (),
        claim_counts: ClaimCounts | None = None,
        latency_ms: int = 0,
    ) -> VerificationDecision:
        """Construct a refusal. The only way refusals are built in this package."""
        return cls(
            outcome=DecisionOutcome.REFUSED,
            strategy=None,
            reason_code=reason_code,
            claims=claims,
            claim_counts=claim_counts or ClaimCounts.not_measured(),
            mechanism=mechanism,
            latency_ms=latency_ms,
            detail=detail,
        )

    @classmethod
    def ground(
        cls,
        strategy: ResponseStrategy,
        *,
        mechanism: str,
        claims: tuple[Claim, ...],
        latency_ms: int = 0,
        detail: str = "",
    ) -> VerificationDecision:
        """Construct a grounded decision."""
        return cls(
            outcome=DecisionOutcome.GROUNDED,
            strategy=strategy,
            reason_code=None,
            claims=claims,
            claim_counts=ClaimCounts.from_claims(claims),
            mechanism=mechanism,
            latency_ms=latency_ms,
            detail=detail,
        )


def parse_claims(raw_claims: Sequence[Mapping[str, Any]]) -> tuple[Claim, ...]:
    """Parse raw verifier claims, failing closed on anything unexpected.

    Raises :class:`VerifierFailure` carrying the reason code that describes the
    specific defect:

    - ``missing_claim_verdict`` — the verdict key is absent or empty;
    - ``unknown_claim_verdict`` — the verdict is outside the controlled set;
    - ``malformed_verifier_output`` — the claim is not a mapping, has no usable
      text, or violates a claim-level invariant.

    There is deliberately no coercion and no default anywhere in this function.
    Every branch that could plausibly "just take a reasonable guess" instead
    raises, because a reasonable guess about whether a claim was verified is
    the definition of an unverified claim being presented as verified.
    """
    parsed: list[Claim] = []

    for index, raw in enumerate(raw_claims):
        if not isinstance(raw, Mapping):
            raise VerifierFailure(
                f"claim at index {index} is not a mapping",
                reason_code=ReasonCode.MALFORMED_VERIFIER_OUTPUT.value,
            )

        if "verdict" not in raw or raw["verdict"] in (None, ""):
            raise VerifierFailure(
                f"claim at index {index} omits its required verdict field; "
                "there is no default — a missing required field is malformed output",
                reason_code=ReasonCode.MISSING_CLAIM_VERDICT.value,
            )

        raw_verdict = raw["verdict"]
        verdict_name = raw_verdict.value if isinstance(raw_verdict, ClaimVerdict) else raw_verdict
        try:
            verdict = ClaimVerdict(str(verdict_name))
        except ValueError as exc:
            permitted = sorted(v.value for v in ClaimVerdict)
            raise VerifierFailure(
                f"claim at index {index} carries verdict {verdict_name!r}, "
                f"which is outside the controlled vocabulary {permitted}",
                reason_code=ReasonCode.UNKNOWN_CLAIM_VERDICT.value,
            ) from exc

        try:
            parsed.append(
                Claim(
                    text=str(raw.get("text", "")),
                    verdict=verdict,
                    evidence_ref=raw.get("evidence_ref"),
                    states_scope_limitation=bool(raw.get("states_scope_limitation", False)),
                )
            )
        except ValueError as exc:
            raise VerifierFailure(
                f"claim at index {index} is malformed: {exc}",
                reason_code=ReasonCode.MALFORMED_VERIFIER_OUTPUT.value,
            ) from exc

    return tuple(parsed)
