"""Fail-open capture, population provenance, and honest metrics."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from executable_trust.decisions import DecisionRecord
from executable_trust.domain.enums import (
    AuthorizationResult,
    DecisionOutcome,
    Environment,
    Population,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.identifiers import FixedClock, SequentialIdFactory
from executable_trust.domain.models import ClaimCounts
from executable_trust.telemetry import (
    QUALITY_NOTE,
    AlwaysFailingTelemetryStore,
    InMemoryTelemetryStore,
    TelemetryEvent,
    TelemetryRecorder,
    classify_environment,
    classify_population,
    compute_behavior_metrics,
    observed_events,
)

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _decision(**overrides) -> DecisionRecord:
    base = {
        "decision_id": "dec-1",
        "recorded_at": NOW,
        "contract_id": "executable-trust-reference",
        "contract_version": "1.0",
        "correlation_id": "corr-1",
        "subject_id": "avery-stone",
        "request_ref": "handbook/code-review",
        "evidence_set_ref": "ev-1",
        "authorization_result": AuthorizationResult.ALLOWED,
        "outcome": DecisionOutcome.GROUNDED,
        "strategy": ResponseStrategy.DIRECT,
        "reason_code": None,
        "verification_mechanism": "scripted",
        "evidence_count": 1,
        "claim_counts": ClaimCounts(total=1, supported=1, unsupported=0, contradicted=0),
        "latency_ms": 12,
        "population": Population.OBSERVED,
        "environment": Environment.PRODUCTION,
    }
    base.update(overrides)
    return DecisionRecord(**base)


def _event(idx: int, **overrides) -> TelemetryEvent:
    base = {
        "event_id": f"evt-{idx}",
        "captured_at": NOW,
        "decision_id": f"dec-{idx}",
        "correlation_id": f"corr-{idx}",
        "outcome": DecisionOutcome.GROUNDED,
        "strategy": ResponseStrategy.DIRECT,
        "reason_code": None,
        "verification_mechanism": "scripted",
        "evidence_count": 1,
        "claim_counts": ClaimCounts(total=1, supported=1, unsupported=0, contradicted=0),
        "latency_ms": 10 + idx,
        "contract_id": "executable-trust-reference",
        "contract_version": "1.0",
        "environment": Environment.PRODUCTION,
        "population": Population.OBSERVED,
    }
    base.update(overrides)
    return TelemetryEvent(**base)


# ---------------------------------------------------------------------------
# ET-TEL-001 — capture fails open
# ---------------------------------------------------------------------------


def test_capture_failure_does_not_raise(caplog):
    """ET-TEL-001: a telemetry backend failure is swallowed and logged."""
    recorder = TelemetryRecorder(
        AlwaysFailingTelemetryStore(),
        clock=FixedClock(),
        ids=SequentialIdFactory(),
        environment=Environment.PRODUCTION,
        population=Population.OBSERVED,
    )

    with caplog.at_level(logging.WARNING):
        event = recorder.record(_decision())

    assert event is None
    assert recorder.capture_failures == 1
    assert "fail-open" in caplog.text
    assert "governed decision unaffected" in caplog.text


def test_governed_decision_is_unchanged_when_capture_fails(
    make_service, make_request, engineer, good_evidence, supported_claims, clock, ids
):
    """ET-TEL-001: the decision is byte-identical with a dead telemetry backend.

    Two services differing only in their telemetry store must produce the same
    governed outcome. If they do not, capture is on the critical path.
    """
    from executable_trust.verification import ScriptedVerifier

    healthy = make_service(verifier=ScriptedVerifier(claims=supported_claims))
    healthy_result = healthy.handle(make_request(engineer), good_evidence)

    broken_recorder = TelemetryRecorder(
        AlwaysFailingTelemetryStore(),
        clock=clock,
        ids=ids,
        environment=Environment.PRODUCTION,
        population=Population.OBSERVED,
    )
    broken = make_service(verifier=ScriptedVerifier(claims=supported_claims), rec=broken_recorder)
    broken_result = broken.handle(make_request(engineer), good_evidence)

    assert healthy_result.decision == broken_result.decision
    assert healthy_result.telemetry_captured is True
    assert broken_result.telemetry_captured is False
    assert broken_result.decision.outcome is DecisionOutcome.GROUNDED


def test_a_refusal_is_never_promoted_by_capture_failure(
    make_service, make_request, engineer, good_evidence
):
    """ET-TEL-001: fail-open never means fail-permissive."""
    from executable_trust.verification import ScriptedVerifier

    recorder = TelemetryRecorder(
        AlwaysFailingTelemetryStore(),
        clock=FixedClock(),
        ids=SequentialIdFactory(),
        environment=Environment.PRODUCTION,
        population=Population.OBSERVED,
    )
    service = make_service(verifier=ScriptedVerifier(claims=()), rec=recorder)

    result = service.handle(make_request(engineer), good_evidence)

    assert result.decision.outcome is DecisionOutcome.REFUSED
    assert result.decision.reason_code is ReasonCode.EMPTY_CLAIM_SET


# ---------------------------------------------------------------------------
# ET-TEL-002 — population provenance
# ---------------------------------------------------------------------------


def test_unknown_environment_resolves_to_production():
    """ET-TEL-002: conservative classification. Guessing 'probably dev' is the defect."""
    assert classify_environment(None) is Environment.PRODUCTION
    assert classify_environment("") is Environment.PRODUCTION
    assert classify_environment("wat") is Environment.PRODUCTION
    assert classify_environment("test") is Environment.TEST


def test_anything_not_observed_is_synthetic():
    """ET-TEL-002: only the exact string 'observed' yields OBSERVED."""
    assert classify_population("observed") is Population.OBSERVED
    assert classify_population("Observed") is Population.OBSERVED
    assert classify_population(None) is Population.SYNTHETIC
    assert classify_population("real") is Population.SYNTHETIC


def test_test_traffic_is_excluded_from_observed_metrics(contract):
    """ET-TEL-002: this is the contamination the paper's Layer 5 describes.

    A test run writing fixture decisions into the same table would otherwise be
    aggregated into a number reported as production behaviour.
    """
    events = tuple(
        [_event(i) for i in range(10)]
        + [
            _event(100 + i, environment=Environment.TEST, population=Population.SYNTHETIC)
            for i in range(50)
        ]
    )

    observed = observed_events(events, contract)

    assert len(observed) == 10
    metrics = compute_behavior_metrics(events, contract)
    assert metrics.total == 10
    assert metrics.population.synthetic_events_excluded == 50


def test_observed_population_in_a_non_permitted_environment_is_excluded(contract):
    """ET-TEL-002: both axes are filtered, not just the synthetic flag."""
    events = tuple(
        [_event(i) for i in range(10)]
        + [_event(200, environment=Environment.STAGING, population=Population.OBSERVED)]
    )

    metrics = compute_behavior_metrics(events, contract)

    assert metrics.total == 10
    assert metrics.population.other_environment_events_excluded == 1


# ---------------------------------------------------------------------------
# ET-TEL-003 — store facts, not scores
# ---------------------------------------------------------------------------


def test_telemetry_event_rejects_a_confidence_field():
    """ET-TEL-003: no score field exists, and adding one is a validation error.

    Under a refuse-anything-imperfect rule a stored confidence is a constant,
    and a constant rendered as a score is uninformative — which in a trust
    product is dishonest.
    """
    with pytest.raises(ValidationError):
        TelemetryEvent(**{**_event(1).model_dump(), "confidence": 1.0})


def test_telemetry_event_rejects_a_correctness_field():
    """ET-TEL-003: correctness needs ground truth, which runtime does not have."""
    with pytest.raises(ValidationError):
        TelemetryEvent(**{**_event(1).model_dump(), "correct": True})


def test_telemetry_has_no_grounded_boolean():
    """ET-TEL-003: `outcome` is the only meaning of grounded. One field, one meaning."""
    assert "grounded" not in TelemetryEvent.model_fields


def test_refused_event_carries_no_strategy():
    """ET-OUT-002: a null strategy on a refusal is correct, not a gap to be filled."""
    with pytest.raises(ValidationError, match="must not carry a strategy"):
        TelemetryEvent(
            **{
                **_event(1).model_dump(),
                "outcome": DecisionOutcome.REFUSED,
                "strategy": ResponseStrategy.DIRECT,
                "reason_code": ReasonCode.VERIFIER_ERROR,
            }
        )


def test_claim_counts_distinguish_unmeasured_from_empty():
    """ET-TEL-003: None means never checked; 0 means checked and found nothing."""
    assert ClaimCounts.not_measured().measured is False
    assert ClaimCounts.from_claims(()).measured is True
    assert ClaimCounts.from_claims(()).total == 0


# ---------------------------------------------------------------------------
# ET-TEL-004 / ET-TEL-005 — counts always, rates gated
# ---------------------------------------------------------------------------


def test_counts_are_visible_below_the_minimum_sample(contract):
    """ET-TEL-004: a consumer can always see how many decisions there were."""
    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(3)), contract)

    assert metrics.total == 3
    assert metrics.counts["grounded"] == 3
    assert metrics.insufficient_sample is True


def test_rates_are_withheld_below_the_minimum_sample(contract):
    """ET-TEL-005: a 100% rate from three decisions is worse than no number."""
    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(3)), contract)

    assert metrics.grounded_rate is None
    assert metrics.refused_rate is None
    assert metrics.minimum_sample == 10


def test_rate_key_is_present_and_null_not_absent(contract):
    """ET-TEL-005: the payload shape never changes, so consumers do not branch."""
    payload = compute_behavior_metrics(tuple(_event(i) for i in range(3)), contract).model_dump()

    assert "grounded_rate" in payload
    assert payload["grounded_rate"] is None


def test_rates_appear_at_the_minimum_sample(contract):
    """ET-TEL-005: at the threshold the rate is reported."""
    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(10)), contract)

    assert metrics.insufficient_sample is False
    assert metrics.grounded_rate == 1.0


def test_withheld_rate_is_distinguishable_from_a_zero_rate(contract):
    """ET-TEL-005: None and 0.0 are different facts and must not share a value."""
    refusals = tuple(
        _event(
            i,
            outcome=DecisionOutcome.REFUSED,
            strategy=None,
            reason_code=ReasonCode.UNSUPPORTED_CLAIM,
        )
        for i in range(10)
    )
    metrics = compute_behavior_metrics(refusals, contract)

    assert metrics.grounded_rate == 0.0
    assert metrics.refused_rate == 1.0


def test_latency_is_reported_with_its_observation_count(contract):
    """ET-TEL-005: latency is a measurement, not a rate, so it is not gated."""
    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(3)), contract)

    assert metrics.latency_ms_p50 is not None
    assert metrics.latency_observations == 3


def test_faults_are_separated_from_evidence_judgements(contract):
    """ET-TEL-005: 'the checker is unwell' is not 'the evidence did not support it'."""
    events = tuple(
        [
            _event(
                i,
                outcome=DecisionOutcome.REFUSED,
                strategy=None,
                reason_code=ReasonCode.VERIFIER_ERROR,
            )
            for i in range(5)
        ]
        + [
            _event(
                50 + i,
                outcome=DecisionOutcome.REFUSED,
                strategy=None,
                reason_code=ReasonCode.UNSUPPORTED_CLAIM,
            )
            for i in range(5)
        ]
    )

    metrics = compute_behavior_metrics(events, contract)

    assert metrics.counts["faults"] == 5
    assert metrics.fault_rate == 0.5
    assert metrics.reason_code_counts["verifier_error"] == 5
    assert metrics.reason_code_counts["unsupported_claim"] == 5


# ---------------------------------------------------------------------------
# ET-TEL-006 — runtime telemetry makes no quality claim
# ---------------------------------------------------------------------------


def test_metrics_never_report_accuracy(contract):
    """ET-TEL-006: no field may be named accuracy or correctness.

    A tripwire, not a comment. If someone adds an accuracy field to a
    behavioural payload, this fails.
    """
    payload = compute_behavior_metrics(tuple(_event(i) for i in range(10)), contract)
    keys = {k.lower() for k in payload.model_dump()}

    assert "accuracy" not in keys
    assert "correctness" not in keys
    assert "quality_score" not in keys


def test_quality_note_travels_with_the_payload(contract):
    """ET-TEL-006: the caveat ships inside the payload, not only in a document.

    A consumer cannot render the numbers without the boundary being available
    at the point of use.
    """
    metrics = compute_behavior_metrics(tuple(_event(i) for i in range(10)), contract)

    assert metrics.quality_note == QUALITY_NOTE
    assert "offline evaluation baseline" in metrics.quality_note
    assert "never reports accuracy" in metrics.quality_note


def test_store_filters_by_population(contract):
    """ET-TEL-002: filtering happens at the query, not by caller discipline."""
    store = InMemoryTelemetryStore()
    for i in range(3):
        store.append(_event(i))
    store.append(_event(99, environment=Environment.TEST, population=Population.SYNTHETIC))

    assert len(store.all()) == 4
    assert len(store.filtered(population=Population.OBSERVED)) == 3
    assert len(store.filtered(environments=(Environment.TEST,))) == 1
