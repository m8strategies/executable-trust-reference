"""Regression tests for the failure modes the paper documents.

Each test here pins a specific way an enterprise AI system silently stops being
trustworthy. They are grouped by the paper's narrative rather than by module,
because that is how someone reading the paper will look for them.

These are the tests most likely to be deleted by someone who does not
understand why they exist. Each one therefore states what breaks if it is
removed.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from executable_trust.domain.enums import DecisionOutcome, ReasonCode, ResponseStrategy
from executable_trust.evaluation import load_cases
from executable_trust.telemetry import compute_behavior_metrics
from executable_trust.verification import ScriptedVerifier, VerificationDecision, decide
from executable_trust.verification.models import VerifierResponse

pytestmark = pytest.mark.regression


def _response(claims, **kw) -> VerifierResponse:
    return VerifierResponse(
        mechanism="regression",
        claims=tuple(claims),
        answers_question=kw.pop("answers_question", True),
        **kw,
    )


SUPPORTED = {"text": "a claim", "verdict": "SUPPORTED", "evidence_ref": "e1"}


# ---------------------------------------------------------------------------
# The fail-open edge: two individually reasonable defaults that compound
# ---------------------------------------------------------------------------


def test_empty_claim_list_does_not_score_as_fully_verified(contract):
    """ET-VER-001: the paper's Layer 7 defect, first half.

    An empty claim list trivially satisfies "no claim was unsupported". A check
    written as `all(c.verdict == SUPPORTED for c in claims)` returns True for
    an empty list, promoting an answer nothing examined.

    Delete this test and a degenerate verifier response silently grounds every
    answer it touches.
    """
    decision = decide(_response([]), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.EMPTY_CLAIM_SET


def test_missing_verdict_does_not_default_to_supported(contract):
    """ET-VER-002: the paper's Layer 7 defect, second half.

    A missing verdict field defaulting to true is the other half of the
    compound fail-open. Combined with an empty claim list it promotes an
    entirely unchecked answer.
    """
    decision = decide(_response([{"text": "no verdict here"}]), contract)

    assert decision.reason_code is ReasonCode.MISSING_CLAIM_VERDICT


def test_missing_relevance_flag_does_not_default_to_true(contract):
    """ET-VER-008: a permissive default on the relevance field.

    Every claim below is supported. If `answers_question` defaulted to True,
    this would produce a confident grounded answer from a verifier that never
    reported whether the answer was even on topic.

    Delete this test and a verifier that stops emitting one field starts
    grounding everything.
    """
    decision = decide(_response([SUPPORTED], answers_question=None), contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.MALFORMED_VERIFIER_OUTPUT


# ---------------------------------------------------------------------------
# Constant confidence: a score that is mathematically always the same
# ---------------------------------------------------------------------------


def test_no_confidence_score_is_stored_anywhere(contract):
    """ET-TEL-003: the constant-confidence defect.

    Under a refuse-anything-imperfect rule, the verification score of every
    *emitted* answer is 1.0 by construction. Storing and displaying it as
    "confidence: 100%" is technically true and completely uninformative —
    which, in a product about trust, is dishonest.

    The fix is structural: there is no field to populate.
    """
    from executable_trust.decisions import DecisionRecord
    from executable_trust.telemetry import TelemetryEvent

    for model in (DecisionRecord, TelemetryEvent):
        fields = {f.lower() for f in model.model_fields}
        assert "confidence" not in fields
        assert "score" not in fields
        assert "accuracy" not in fields


def test_grounded_is_derived_not_stored(contract):
    """ET-TEL-003: one field, one meaning.

    A boolean beside the outcome can drift from it, and then "grounded" means
    "the outcome was GROUNDED" in one code path and "the behaviour was correct"
    in another. Harmless in a log; a contradiction in a persisted table.
    """
    decision = decide(_response([SUPPORTED]), contract)

    assert decision.grounded is True  # a derived property
    assert "grounded" not in VerificationDecision.model_fields


# ---------------------------------------------------------------------------
# Small samples presented as meaningful rates
# ---------------------------------------------------------------------------


def test_three_decisions_do_not_produce_a_hundred_percent_rate(contract):
    """ET-TEL-005: a rate from three observations is noise wearing a decimal point.

    Delete this test and a dashboard shows "100% grounded" on the third day of
    a pilot.
    """
    from tests.unit.test_telemetry_and_metrics import _event

    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(3)), contract)

    assert metrics.counts["grounded"] == 3
    assert metrics.grounded_rate is None
    assert metrics.insufficient_sample is True


# ---------------------------------------------------------------------------
# Behavioural telemetry represented as quality
# ---------------------------------------------------------------------------


def test_runtime_metrics_cannot_be_read_as_a_quality_claim(contract):
    """ET-TEL-006: blending "how often we answered" with "how often we were right".

    This is where Executable Trust reverts to governance as marketing. The
    payload carries its own boundary statement so the number cannot travel
    without it.
    """
    from tests.unit.test_telemetry_and_metrics import _event

    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(10)), contract)

    assert "accuracy" not in {k.lower() for k in metrics.model_dump()}
    assert "offline evaluation baseline" in metrics.quality_note


# ---------------------------------------------------------------------------
# Test traffic contaminating operational telemetry
# ---------------------------------------------------------------------------


def test_test_traffic_cannot_enter_an_observed_metric(contract):
    """ET-TEL-002: a suite that exercises the real path writes real-looking rows.

    Without population provenance, a dashboard faithfully aggregates a mixture
    of real behaviour and fixtures and reports a number true of neither.
    """
    from executable_trust.domain.enums import Environment, Population
    from tests.unit.test_telemetry_and_metrics import _event

    real = tuple(_event(i) for i in range(10))
    fixtures = tuple(
        _event(100 + i, environment=Environment.TEST, population=Population.SYNTHETIC)
        for i in range(1000)
    )

    metrics = compute_behavior_metrics(real + fixtures, contract)

    assert metrics.total == 10
    assert metrics.population.synthetic_events_excluded == 1000


# ---------------------------------------------------------------------------
# Partial-answer repair (amendment v1.0-A1)
# ---------------------------------------------------------------------------


def test_partially_supported_answer_is_refused_not_repaired(contract):
    """ET-VER-004: the amendment's ratified rule.

    A repair produced by the same mechanism that produced the flawed answer is
    itself an unverified generation. The system refuses and asks again rather
    than patching and hoping.
    """
    decision = decide(
        _response([SUPPORTED, {"text": "an invention", "verdict": "UNSUPPORTED"}]),
        contract,
    )

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.UNSUPPORTED_CLAIM
    # No repaired answer is offered anywhere on the refusal path.
    assert decision.strategy is None


# ---------------------------------------------------------------------------
# Verification bypass under pressure
# ---------------------------------------------------------------------------


def test_no_configuration_disables_verification(contract, good_evidence):
    """ET-RES-002: there is no kill switch.

    The most tempting change under production pressure is a flag that skips
    verification to keep answering. This package deliberately provides none,
    and the circuit breaker's only permitted moves are escalate and refuse.
    """
    verifier = ScriptedVerifier(claims=())
    response = verifier.verify("any answer", good_evidence, "any question")
    decision = decide(response, contract)

    assert decision.outcome is DecisionOutcome.REFUSED


# ---------------------------------------------------------------------------
# Golden-set integrity
# ---------------------------------------------------------------------------


def test_every_golden_case_is_labelled_synthetic(repo_root):
    """Every fixture, case, and result in this repository is synthetic."""
    cases = load_cases(repo_root / "evaluation" / "golden_set.jsonl")

    assert len(cases) >= 20
    assert all(c.synthetic for c in cases)


def test_golden_set_covers_the_documented_failure_modes(repo_root):
    """The golden set exercises each documented mode, not only the happy path."""
    cases = load_cases(repo_root / "evaluation" / "golden_set.jsonl")
    categories = {c.category for c in cases}

    required = {
        "grounded-direct",
        "grounded-bounded",
        "insufficient-evidence",
        "unsupported-claim",
        "contradicted-claim",
        "no-supported-claims",
        "empty-claim-set",
        "irrelevant-answer",
        "malformed-verifier-output",
        "verifier-exception",
        "verifier-timeout",
        "authorization-denied",
        "evidence-provenance-invalid",
        "unknown-contract",
        "unratified-contract",
        "near-miss",
    }

    assert required <= categories, sorted(required - categories)


def test_a_refused_expectation_cannot_name_a_strategy():
    """ET-OUT-002: a malformed expectation cannot enter the golden set.

    Without this, a case could expect a refusal *with* a strategy and would
    fail forever for a reason unrelated to the code under test.
    """
    from executable_trust.evaluation.models import CaseRequest, EvaluationCase

    with pytest.raises(ValidationError, match="must not name a strategy"):
        EvaluationCase(
            case_id="99-bad-expectation",
            category="near-miss",
            synthetic=True,
            request=CaseRequest(actor="a", resource="r", question="q"),
            applicable_contract_version="1.0",
            expected_outcome=DecisionOutcome.REFUSED,
            expected_strategy=ResponseStrategy.DIRECT,
            expected_reason_code=ReasonCode.UNSUPPORTED_CLAIM,
            rationale="a deliberately malformed expectation",
        )
