"""The fail-closed decision function.

Every test here names the contract rule identifier it pins, which is what the
traceability validator scans for. A test that does not name its rule is a test
nobody can trace back to the document that required it.
"""

from __future__ import annotations

import pytest

from executable_trust.domain.enums import (
    ClaimVerdict,
    DecisionOutcome,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.errors import VerifierFailure
from executable_trust.verification.decision_function import decide
from executable_trust.verification.models import (
    VerificationDecision,
    VerifierResponse,
    parse_claims,
)

MECHANISM = "test-verifier"


def _response(claims, *, answers_question=True, truncated=False) -> VerifierResponse:
    return VerifierResponse(
        mechanism=MECHANISM,
        claims=tuple(claims),
        answers_question=answers_question,
        truncated=truncated,
    )


def _supported(text="a supported claim", *, scope=False):
    return {
        "text": text,
        "verdict": "SUPPORTED",
        "evidence_ref": "e1",
        "states_scope_limitation": scope,
    }


# ---------------------------------------------------------------------------
# ET-VER-001 — an empty claim collection refuses
# ---------------------------------------------------------------------------


def test_empty_claim_set_refuses(contract):
    """ET-VER-001: zero claims means nothing was verified.

    This is the fail-open edge the paper's Layer 7 narrative describes: an
    empty list trivially satisfies "no claim was unsupported", so a naive check
    scores it as fully verified.
    """
    decision = decide(_response([]), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.EMPTY_CLAIM_SET
    assert decision.strategy is None


# ---------------------------------------------------------------------------
# ET-VER-002 / ET-VER-003 — missing and unknown verdicts
# ---------------------------------------------------------------------------


def test_missing_verdict_refuses(contract):
    """ET-VER-002: a claim with no verdict field fails closed, never defaults."""
    decision = decide(_response([{"text": "a claim with no verdict"}]), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.MISSING_CLAIM_VERDICT


def test_empty_string_verdict_is_treated_as_missing(contract):
    """ET-VER-002: an empty verdict is absent, not a value to be interpreted."""
    decision = decide(_response([{"text": "a claim", "verdict": ""}]), contract)

    assert decision.reason_code is ReasonCode.MISSING_CLAIM_VERDICT


def test_unknown_verdict_refuses(contract):
    """ET-VER-003: a verdict outside the controlled vocabulary is not coerced."""
    decision = decide(_response([{"text": "a claim", "verdict": "PROBABLY_FINE"}]), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.UNKNOWN_CLAIM_VERDICT


def test_parse_claims_names_the_offending_index():
    """ET-VER-003: the failure identifies which claim was bad, not just that one was."""
    with pytest.raises(VerifierFailure) as exc:
        parse_claims([_supported(), {"text": "bad", "verdict": "MAYBE"}])

    assert "index 1" in str(exc.value)
    assert exc.value.reason_code == ReasonCode.UNKNOWN_CLAIM_VERDICT.value


# ---------------------------------------------------------------------------
# ET-VER-004 / ET-VER-005 — unsupported, contradicted, and nothing supported
# ---------------------------------------------------------------------------


def test_unsupported_claim_refuses_the_whole_answer(contract):
    """ET-VER-004: a partially supported answer is refused, never repaired in place."""
    decision = decide(
        _response([_supported(), {"text": "an invention", "verdict": "UNSUPPORTED"}]),
        contract,
    )

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.UNSUPPORTED_CLAIM
    assert decision.strategy is None


def test_contradicted_claim_refuses(contract):
    """ET-VER-004: contradiction is treated as severely as absence."""
    decision = decide(
        _response([_supported(), {"text": "the opposite", "verdict": "CONTRADICTED"}]),
        contract,
    )

    assert decision.reason_code is ReasonCode.UNSUPPORTED_CLAIM


def test_no_supported_claims_refuses(contract):
    """ET-VER-005: when nothing is supported, a distinct code is recorded.

    Separated from ET-VER-004 so an operator can tell "retrieval returned
    something useless" from "generation embellished a good answer".
    """
    decision = decide(
        _response(
            [
                {"text": "claim one", "verdict": "UNSUPPORTED"},
                {"text": "claim two", "verdict": "UNSUPPORTED"},
            ]
        ),
        contract,
    )

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.NO_SUPPORTED_CLAIMS


def test_all_contradicted_refuses_as_no_supported_claims(contract):
    """ET-VER-005: evaluated before ET-VER-004, so an all-rejected answer lands here."""
    decision = decide(_response([{"text": "the opposite", "verdict": "CONTRADICTED"}]), contract)

    assert decision.reason_code is ReasonCode.NO_SUPPORTED_CLAIMS


# ---------------------------------------------------------------------------
# ET-VER-006 — relevance
# ---------------------------------------------------------------------------


def test_irrelevant_answer_refuses(contract):
    """ET-VER-006: a truthful statement about something else is not an answer."""
    decision = decide(_response([_supported()], answers_question=False), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.DOES_NOT_ADDRESS_QUESTION


def test_missing_relevance_field_is_malformed_not_implied_yes(contract):
    """ET-VER-008: a missing answers_question is malformed output, never a default True.

    The single most important assertion in this file. A permissive default
    would mean a verifier that silently stopped emitting the field promoted
    every answer it saw.
    """
    decision = decide(_response([_supported()], answers_question=None), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.MALFORMED_VERIFIER_OUTPUT
    assert "not an implied yes" in decision.detail


# ---------------------------------------------------------------------------
# ET-VER-007 — strategy selection, the only grounded exit
# ---------------------------------------------------------------------------


def test_fully_supported_answer_is_grounded_direct(contract):
    """ET-VER-007: no scope limitation stated selects DIRECT."""
    decision = decide(_response([_supported(), _supported("another")]), contract)

    assert decision.outcome is DecisionOutcome.GROUNDED
    assert decision.strategy is ResponseStrategy.DIRECT
    assert decision.reason_code is None
    assert decision.grounded is True


def test_scope_limitation_selects_bounded(contract):
    """ET-VER-007: any claim stating a limitation selects BOUNDED."""
    decision = decide(
        _response([_supported(), _supported("the evidence does not cover X", scope=True)]),
        contract,
    )

    assert decision.outcome is DecisionOutcome.GROUNDED
    assert decision.strategy is ResponseStrategy.BOUNDED


def test_claim_counts_are_recorded_on_a_grounded_decision(contract):
    """ET-VER-007: counts distinguish measured-and-empty from never-measured."""
    decision = decide(_response([_supported(), _supported("two")]), contract)

    assert decision.claim_counts.total == 2
    assert decision.claim_counts.supported == 2
    assert decision.claim_counts.measured is True


# ---------------------------------------------------------------------------
# ET-VER-008 / ET-VER-011 — malformed and truncated output
# ---------------------------------------------------------------------------


def test_non_mapping_claim_is_malformed():
    """ET-VER-008: verifier output that is not the contract's claim shape refuses.

    Tested against ``parse_claims`` directly rather than through ``decide``:
    ``VerifierResponse`` already rejects a non-mapping claim at its own model
    boundary, so this is defence in depth for a caller that parses raw output
    without going through the response model first.
    """
    with pytest.raises(VerifierFailure) as exc:
        parse_claims(["not a mapping"])

    assert exc.value.reason_code == ReasonCode.MALFORMED_VERIFIER_OUTPUT.value
    assert "index 0" in str(exc.value)


def test_truncated_output_refuses_before_parsing(contract):
    """ET-VER-011: truncation is detected before claims are evaluated.

    The claims that arrived are all supported. A system that parsed first would
    see a clean set and ground the answer, having never examined the tail where
    the unsupported claim would have been.
    """
    decision = decide(_response([_supported()], truncated=True), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.VERIFIER_OUTPUT_TRUNCATED
    assert decision.claim_counts.measured is False


# ---------------------------------------------------------------------------
# ET-OUT-001 / ET-OUT-002 / ET-OUT-003 — the outcome/strategy relation
# ---------------------------------------------------------------------------


def test_grounded_decision_requires_a_strategy():
    """ET-OUT-001: a GROUNDED decision cannot be constructed without a strategy."""
    with pytest.raises(ValueError, match="ET-OUT-001"):
        VerificationDecision(outcome=DecisionOutcome.GROUNDED, strategy=None, mechanism=MECHANISM)


def test_refused_decision_forbids_a_strategy():
    """ET-OUT-002: REFUSED is an outcome, never a strategy.

    Pinned explicitly because the pressure to add a third "refusal" strategy —
    so a telemetry column is never null — is real and recurring.
    """
    with pytest.raises(ValueError, match="ET-OUT-002"):
        VerificationDecision(
            outcome=DecisionOutcome.REFUSED,
            strategy=ResponseStrategy.DIRECT,
            reason_code=ReasonCode.VERIFIER_ERROR,
            mechanism=MECHANISM,
        )


def test_refused_decision_requires_a_reason_code():
    """ET-OUT-003: a refusal that cannot say why is not auditable."""
    with pytest.raises(ValueError, match="ET-OUT-003"):
        VerificationDecision(
            outcome=DecisionOutcome.REFUSED, strategy=None, reason_code=None, mechanism=MECHANISM
        )


def test_grounded_decision_forbids_a_reason_code():
    """ET-OUT-003: reason codes explain refusals; a grounded answer needs no excuse."""
    with pytest.raises(ValueError, match="ET-OUT-003"):
        VerificationDecision(
            outcome=DecisionOutcome.GROUNDED,
            strategy=ResponseStrategy.DIRECT,
            reason_code=ReasonCode.UNSUPPORTED_CLAIM,
            mechanism=MECHANISM,
        )


def test_unsupported_claim_may_not_cite_evidence():
    """ET-VER-004: citing evidence for a rejected claim is a contradiction in terms."""
    with pytest.raises(VerifierFailure) as exc:
        parse_claims([{"text": "x", "verdict": "UNSUPPORTED", "evidence_ref": "e1"}])

    assert exc.value.reason_code == ReasonCode.MALFORMED_VERIFIER_OUTPUT.value


def test_verdict_vocabulary_is_exactly_three_members():
    """ET-OUT-001: `verdict` is reserved for claim-level classification only."""
    assert {v.value for v in ClaimVerdict} == {"SUPPORTED", "UNSUPPORTED", "CONTRADICTED"}


def test_strategy_vocabulary_is_exactly_two_members():
    """ET-OUT-002: exactly two strategies, both meaningful only when GROUNDED."""
    assert {s.value for s in ResponseStrategy} == {"DIRECT", "BOUNDED"}
