"""Authorization, the evidence gate, and verification resilience."""

from __future__ import annotations

import pytest

from executable_trust.authorization import DeterministicAuthorizer
from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import EvidenceQuality, ReasonCode
from executable_trust.domain.errors import VerifierFailure, VerifierUnavailable
from executable_trust.evidence import EvidenceItem, EvidenceSet, check_provenance, evaluate_gate
from executable_trust.verification import (
    FaultInjectingVerifier,
    ResilientVerifier,
    ScriptedVerifier,
    decide,
)

# ---------------------------------------------------------------------------
# ET-AUTH-001 — authorization precedes retrieval
# ---------------------------------------------------------------------------


def test_granted_role_is_allowed(engineer):
    """ET-AUTH-001: a granted role reaches its resource."""
    decision = DeterministicAuthorizer().authorize(engineer, "handbook/code-review")

    assert decision.allowed is True


def test_role_without_grants_is_denied(contractor):
    """ET-AUTH-001: a recognised role with no grants is denied, not defaulted open."""
    decision = DeterministicAuthorizer().authorize(contractor, "handbook/code-review")

    assert decision.allowed is False
    assert "not granted" in decision.reason


def test_role_denied_for_ungranted_resource(engineer):
    """ET-AUTH-001: policy is consulted per resource, not per identity."""
    decision = DeterministicAuthorizer().authorize(engineer, "architecture-standards/retention")

    assert decision.allowed is False


def test_unknown_role_is_denied():
    """ET-AUTH-001: deny by default. An unrecognised role is not a permitted one."""
    from executable_trust.domain.enums import ActorType
    from executable_trust.domain.models import Actor

    stranger = Actor(actor_id="x", actor_type=ActorType.PRINCIPAL, role="not-a-real-role")
    decision = DeterministicAuthorizer().authorize(stranger, "handbook/code-review")

    assert decision.allowed is False
    assert "not recognised" in decision.reason


def test_system_actor_is_denied(system_actor):
    """ET-AUTH-001: governed reads happen on behalf of an accountable principal."""
    decision = DeterministicAuthorizer().authorize(system_actor, "handbook/code-review")

    assert decision.allowed is False


def test_wildcard_does_not_grant_the_collection_itself(engineer):
    """ET-AUTH-001: `handbook/*` grants the contents, not the collection record."""
    assert DeterministicAuthorizer().authorize(engineer, "handbook").allowed is False
    assert DeterministicAuthorizer().authorize(engineer, "handbook/x").allowed is True


# ---------------------------------------------------------------------------
# ET-EV-001 — evidence sufficiency
# ---------------------------------------------------------------------------


def test_empty_retrieval_is_insufficient(contract: TrustContract):
    """ET-EV-001: nothing retrieved cannot clear the bar."""
    result = evaluate_gate(EvidenceSet(evidence_set_ref="e"), contract)

    assert result.sufficient is False
    assert result.quality is EvidenceQuality.EMPTY


def test_weak_relevance_is_insufficient(contract: TrustContract):
    """ET-EV-001: weakly related evidence is more dangerous than none."""
    evidence = EvidenceSet(
        evidence_set_ref="e",
        items=(
            EvidenceItem(
                evidence_id="a",
                text="tangential",
                relevance_score=0.21,
                provenance="governed_corpus",
            ),
        ),
    )
    result = evaluate_gate(evidence, contract)

    assert result.sufficient is False
    assert result.quality is EvidenceQuality.INSUFFICIENT
    assert "0.350" in result.detail


def test_sufficient_evidence_clears_the_gate(contract: TrustContract, good_evidence):
    """ET-EV-001: evidence above the bar proceeds."""
    result = evaluate_gate(good_evidence, contract)

    assert result.sufficient is True
    assert result.quality is EvidenceQuality.SUFFICIENT


def test_gate_reports_observed_values_beside_thresholds(contract: TrustContract, good_evidence):
    """ET-EV-001: a refusal must be explainable without re-running the gate."""
    result = evaluate_gate(good_evidence, contract)

    assert result.threshold_score == contract.evidence.gate.min_similarity_score
    assert result.observed_top_score == 0.9


# ---------------------------------------------------------------------------
# ET-EV-002 — evidence provenance
# ---------------------------------------------------------------------------


def test_unrecognised_provenance_is_rejected(contract: TrustContract):
    """ET-EV-002: evidence whose origin is unknown is not evidence.

    Deliberately given a very high relevance score: the provenance check must
    run independently of relevance, or a well-scoring untrusted passage slips
    through.
    """
    evidence = EvidenceSet(
        evidence_set_ref="e",
        items=(
            EvidenceItem(
                evidence_id="a",
                text="highly relevant",
                relevance_score=0.99,
                provenance="unverified_scrape",
            ),
        ),
    )

    failure = check_provenance(evidence, contract)

    assert failure is not None
    assert "unverified_scrape" in failure


def test_permitted_provenance_passes(contract: TrustContract, good_evidence):
    """ET-EV-002: a permitted source is accepted."""
    assert check_provenance(good_evidence, contract) is None


# ---------------------------------------------------------------------------
# ET-VER-009 / ET-VER-010 — verifier faults fail closed
# ---------------------------------------------------------------------------


def test_verifier_exception_fails_closed(contract: TrustContract, good_evidence):
    """ET-VER-009: a raising verifier never produces a grounded answer."""
    verifier = FaultInjectingVerifier(ScriptedVerifier(), "raise")

    with pytest.raises(VerifierFailure) as exc:
        verifier.verify("an answer", good_evidence, "a question")

    assert exc.value.reason_code == ReasonCode.VERIFIER_ERROR.value


def test_verifier_timeout_fails_closed(contract: TrustContract, good_evidence):
    """ET-VER-010: a timeout carries its own code, distinct from a general fault."""
    verifier = FaultInjectingVerifier(ScriptedVerifier(), "timeout")

    with pytest.raises(VerifierFailure) as exc:
        verifier.verify("an answer", good_evidence, "a question")

    assert exc.value.reason_code == ReasonCode.VERIFIER_TIMEOUT.value


def test_truncated_response_is_flagged(contract: TrustContract, good_evidence, supported_claims):
    """ET-VER-011: the wrapper marks truncation rather than silently trimming."""
    verifier = FaultInjectingVerifier(ScriptedVerifier(claims=supported_claims), "truncated")
    response = verifier.verify("an answer", good_evidence, "a question")

    assert response.truncated is True
    assert decide(response, contract).reason_code is ReasonCode.VERIFIER_OUTPUT_TRUNCATED


# ---------------------------------------------------------------------------
# ET-RES-001 / ET-RES-002 — the circuit breaker
# ---------------------------------------------------------------------------


def test_healthy_primary_serves_traffic(contract: TrustContract, good_evidence, supported_claims):
    """ET-RES-001: no escalation while the primary is healthy."""
    primary = ScriptedVerifier(claims=supported_claims, name="primary")
    resilient = ResilientVerifier(primary, contract)

    response = resilient.verify("a", good_evidence, "q")

    assert response.mechanism == "primary"
    assert resilient.is_tripped("primary") is False


class _HealthyButRaising:
    """A mechanism that claims health and then faults.

    The realistic failure: a dependency whose health probe still succeeds while
    its actual calls are failing. A verifier that honestly reports itself
    unhealthy is the easy case.
    """

    name = "primary"
    healthy = True

    def verify(self, answer, evidence, question):
        raise VerifierFailure("upstream fault", reason_code=ReasonCode.VERIFIER_ERROR.value)


def test_unhealthy_primary_is_skipped_before_being_called(
    contract: TrustContract, good_evidence, supported_claims
):
    """ET-RES-001: a mechanism that reports itself unhealthy is not called at all.

    Escalation happens before the failing call, not after it, so a known-bad
    dependency costs nothing.
    """
    primary = FaultInjectingVerifier(ScriptedVerifier(name="primary"), "unavailable")
    conservative = ScriptedVerifier(claims=supported_claims, name="conservative")
    resilient = ResilientVerifier(primary, contract, conservative=conservative)

    response = resilient.verify("a", good_evidence, "q")

    assert response.mechanism == "conservative"
    assert any(e.event == "reported_unhealthy" for e in resilient.events)


def test_breaker_trips_and_escalates_after_repeated_faults(
    contract: TrustContract, good_evidence, supported_claims
):
    """ET-RES-001: a primary that claims health but faults trips the breaker.

    Faults propagate while the breaker is still learning — the decision
    function converts each into a fail-closed refusal — and once the observed
    rate crosses the contract threshold, traffic moves to the conservative
    mechanism.
    """
    conservative = ScriptedVerifier(claims=supported_claims, name="conservative")
    resilient = ResilientVerifier(_HealthyButRaising(), contract, conservative=conservative)

    minimum = contract.resilience[0].minimum_observations  # type: ignore[attr-defined]
    for _ in range(minimum):
        with pytest.raises(VerifierFailure):
            resilient.verify("a", good_evidence, "q")

    assert resilient.is_tripped("primary") is True
    assert any(e.event == "escalated" for e in resilient.events)

    response = resilient.verify("a", good_evidence, "q")
    assert response.mechanism == "conservative"


def test_single_fault_does_not_trip_the_breaker(
    contract: TrustContract, good_evidence, supported_claims
):
    """ET-RES-001: one fault is not a fault *rate*. A hair trigger is its own outage."""
    primary = ScriptedVerifier(claims=supported_claims, name="primary")
    resilient = ResilientVerifier(primary, contract)
    resilient.health("primary").record(faulted=True)

    assert resilient.is_tripped("primary") is False


def test_refuses_when_no_verifier_is_available(contract: TrustContract, good_evidence):
    """ET-RES-002: verification is never skipped to keep answering."""
    primary = FaultInjectingVerifier(ScriptedVerifier(name="primary"), "unavailable")
    resilient = ResilientVerifier(primary, contract)

    with pytest.raises(VerifierUnavailable):
        resilient.verify("a", good_evidence, "q")


def test_breaker_never_returns_an_unverified_response(contract: TrustContract, good_evidence):
    """ET-RES-002: with no healthy mechanism the only outcome is a refusal.

    The breaker's permitted moves are escalate and refuse. Returning a
    synthesised "assume it is fine" response is not among them.
    """
    primary = FaultInjectingVerifier(ScriptedVerifier(name="primary"), "unavailable")
    conservative = FaultInjectingVerifier(ScriptedVerifier(name="fallback"), "unavailable")
    resilient = ResilientVerifier(primary, contract, conservative=conservative)

    with pytest.raises(VerifierUnavailable):
        resilient.verify("a", good_evidence, "q")
