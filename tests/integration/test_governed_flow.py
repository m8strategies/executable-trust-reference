"""End-to-end governed request path.

The property most of these tests are really about: **the expensive step never
runs on a refusal path.** Refusals are short-circuits, not error handlers, and
that is checkable only if the generator records whether it was called.
"""

from __future__ import annotations

from executable_trust.decisions import refused_for
from executable_trust.domain.enums import (
    AuthorizationResult,
    DecisionOutcome,
    Environment,
    Population,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.evidence import EvidenceItem, EvidenceSet
from executable_trust.verification import ScriptedVerifier


def _evidence(score: float = 0.9, provenance: str = "governed_corpus") -> EvidenceSet:
    return EvidenceSet(
        evidence_set_ref="ev-1",
        items=(
            EvidenceItem(
                evidence_id="hb-1",
                text="An approved code review remains valid for 14 calendar days.",
                relevance_score=score,
                provenance=provenance,
            ),
        ),
    )


# ---------------------------------------------------------------------------
# The grounded path
# ---------------------------------------------------------------------------


def test_fully_supported_request_is_grounded(
    make_service, make_request, engineer, supported_claims, generator, decision_store
):
    """ET-VER-007: the happy path produces a grounded, recorded decision."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(engineer), _evidence())

    assert result.decision.outcome is DecisionOutcome.GROUNDED
    assert result.decision.strategy is ResponseStrategy.DIRECT
    assert result.generation_invoked is True
    assert generator.calls == 1
    assert len(decision_store) == 1

    record = result.record
    assert record.authorization_result is AuthorizationResult.ALLOWED
    assert record.contract_version == "1.0"
    assert record.evidence_count == 1
    assert record.claim_counts.supported == 1
    assert record.population is Population.OBSERVED
    assert record.environment is Environment.PRODUCTION


def test_decision_record_carries_full_provenance(
    make_service, make_request, engineer, supported_claims
):
    """Every field needed to explain the decision later is present."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))
    record = service.handle(make_request(engineer), _evidence()).record

    assert record.correlation_id == "corr-test-1"
    assert record.subject_id == "avery-stone"
    assert record.request_ref == "handbook/code-review"
    assert record.evidence_set_ref == "ev-1"
    assert record.verification_mechanism
    assert record.reason_code is None


# ---------------------------------------------------------------------------
# ET-AUTH-001 — authorization denial prevents retrieval and generation
# ---------------------------------------------------------------------------


def test_authorization_denial_prevents_generation(
    make_service, make_request, contractor, supported_claims, generator
):
    """ET-AUTH-001: a denied request exits before the generator is invoked."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(contractor), _evidence())

    assert refused_for(result, ReasonCode.AUTHORIZATION_DENIED)
    assert result.generation_invoked is False
    assert generator.calls == 0


def test_authorization_denial_records_no_evidence(
    make_service, make_request, contractor, supported_claims
):
    """ET-AUTH-001: authorization precedes retrieval, so nothing was read."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    record = service.handle(make_request(contractor), _evidence()).record

    assert record.authorization_result is AuthorizationResult.DENIED
    assert record.evidence_count == 0
    assert record.claim_counts.measured is False


# ---------------------------------------------------------------------------
# ET-EV-001 / ET-EV-002 — evidence gates prevent generation
# ---------------------------------------------------------------------------


def test_insufficient_evidence_prevents_generation(
    make_service, make_request, engineer, supported_claims, generator
):
    """ET-EV-001: the refusal is pre-generation, not post-hoc discarding."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(engineer), _evidence(score=0.2))

    assert refused_for(result, ReasonCode.INSUFFICIENT_EVIDENCE)
    assert result.generation_invoked is False
    assert generator.calls == 0


def test_empty_evidence_prevents_generation(
    make_service, make_request, engineer, supported_claims, generator
):
    """ET-EV-001: nothing retrieved cannot be answered from."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(engineer), EvidenceSet(evidence_set_ref="ev-empty"))

    assert refused_for(result, ReasonCode.INSUFFICIENT_EVIDENCE)
    assert generator.calls == 0


def test_invalid_provenance_prevents_generation(
    make_service, make_request, engineer, supported_claims, generator
):
    """ET-EV-002: high relevance does not rescue unknown provenance."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(
        make_request(engineer), _evidence(score=0.99, provenance="unverified_scrape")
    )

    assert refused_for(result, ReasonCode.EVIDENCE_PROVENANCE_INVALID)
    assert result.generation_invoked is False
    assert generator.calls == 0


# ---------------------------------------------------------------------------
# ET-CON-001 / ET-CON-002 — contract resolution precedes everything
# ---------------------------------------------------------------------------


def test_unknown_contract_prevents_everything(
    make_service, make_request, engineer, supported_claims, generator
):
    """ET-CON-001: without a governing contract nothing else runs."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(engineer, contract_version="9.9"), _evidence())

    assert refused_for(result, ReasonCode.CONTRACT_VERSION_UNKNOWN)
    assert result.generation_invoked is False
    assert generator.calls == 0
    # The record still names the version that was asked for; blanking it would
    # lose the only fact that explains the refusal.
    assert result.record.contract_version == "9.9"


def test_unratified_contract_prevents_everything(
    make_service, make_request, engineer, supported_claims, generator
):
    """ET-CON-002: a draft contract governs nothing."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))

    result = service.handle(make_request(engineer, contract_version="0.9"), _evidence())

    assert refused_for(result, ReasonCode.CONTRACT_NOT_RATIFIED)
    assert generator.calls == 0


# ---------------------------------------------------------------------------
# Verification is never bypassed
# ---------------------------------------------------------------------------


def test_verification_is_never_bypassed(make_service, make_request, engineer, good_evidence):
    """ET-VER-001: a verifier returning nothing yields a refusal, not a pass-through.

    There is no configuration, flag, or code path in this package that emits an
    answer without a verification decision behind it.
    """
    service = make_service(verifier=ScriptedVerifier(claims=()))

    result = service.handle(make_request(engineer), good_evidence)

    assert result.decision.outcome is DecisionOutcome.REFUSED
    assert result.decision.reason_code is ReasonCode.EMPTY_CLAIM_SET
    assert result.generation_invoked is True  # generation ran; the answer was refused


def test_verifier_exception_becomes_a_fail_closed_refusal(
    make_service, make_request, engineer, good_evidence, supported_claims
):
    """ET-VER-009: an exception in the verifier never escapes as a grounded answer."""
    from executable_trust.verification import FaultInjectingVerifier

    service = make_service(
        verifier=FaultInjectingVerifier(ScriptedVerifier(claims=supported_claims), "raise")
    )

    result = service.handle(make_request(engineer), good_evidence)

    assert refused_for(result, ReasonCode.VERIFIER_ERROR)


def test_verifier_timeout_becomes_a_fail_closed_refusal(
    make_service, make_request, engineer, good_evidence, supported_claims
):
    """ET-VER-010: a timeout is a refusal with its own reason code."""
    from executable_trust.verification import FaultInjectingVerifier

    service = make_service(
        verifier=FaultInjectingVerifier(ScriptedVerifier(claims=supported_claims), "timeout")
    )

    result = service.handle(make_request(engineer), good_evidence)

    assert refused_for(result, ReasonCode.VERIFIER_TIMEOUT)


def test_unavailable_verifier_becomes_a_fail_closed_refusal(
    make_service, make_request, engineer, good_evidence
):
    """ET-RES-002: no healthy verifier means refuse, never answer unverified."""
    from executable_trust.verification import FaultInjectingVerifier

    service = make_service(verifier=FaultInjectingVerifier(ScriptedVerifier(), "unavailable"))

    result = service.handle(make_request(engineer), good_evidence)

    assert refused_for(result, ReasonCode.NO_VERIFIER_AVAILABLE)


# ---------------------------------------------------------------------------
# Telemetry follows, and cannot lead
# ---------------------------------------------------------------------------


def test_telemetry_event_mirrors_the_decision(
    make_service, make_request, engineer, supported_claims, telemetry_store
):
    """ET-TEL-003: the event records the same facts, with no added judgement."""
    service = make_service(verifier=ScriptedVerifier(claims=supported_claims))
    result = service.handle(make_request(engineer), _evidence())

    events = telemetry_store.all()
    assert len(events) == 1

    event = events[0]
    assert event.decision_id == result.record.decision_id
    assert event.outcome is result.decision.outcome
    assert event.strategy is result.decision.strategy
    assert event.contract_version == "1.0"
    assert event.evidence_quality is not None


def test_synthetic_service_marks_its_events(
    make_service, make_request, engineer, supported_claims, clock, ids
):
    """ET-TEL-002: a non-production deployment stamps its own population."""
    from executable_trust.telemetry import InMemoryTelemetryStore, TelemetryRecorder

    store = InMemoryTelemetryStore()
    recorder = TelemetryRecorder(
        store,
        clock=clock,
        ids=ids,
        environment=Environment.TEST,
        population=Population.SYNTHETIC,
    )
    service = make_service(
        verifier=ScriptedVerifier(claims=supported_claims),
        rec=recorder,
        environment=Environment.TEST,
        population=Population.SYNTHETIC,
    )

    service.handle(make_request(engineer), _evidence())

    event = store.all()[0]
    assert event.environment is Environment.TEST
    assert event.population is Population.SYNTHETIC
