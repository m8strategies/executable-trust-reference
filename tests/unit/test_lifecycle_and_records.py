"""Decision-record immutability and the append-only lifecycle."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from executable_trust.decisions import DecisionRecord, InMemoryDecisionStore
from executable_trust.domain.enums import (
    ActorType,
    AuthorizationResult,
    DecisionOutcome,
    Environment,
    LifecycleState,
    Population,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.errors import (
    ImmutableRecordViolation,
    InvalidTransition,
    MissingAccountableReview,
)
from executable_trust.domain.models import Actor, ClaimCounts
from executable_trust.lifecycle import project_state, state_at

NOW = datetime(2026, 1, 1, tzinfo=UTC)


def _record(decision_id: str = "dec-1", **overrides) -> DecisionRecord:
    base = {
        "decision_id": decision_id,
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
        "claim_counts": ClaimCounts.from_claims(()),
        "latency_ms": 12,
        "population": Population.OBSERVED,
        "environment": Environment.PRODUCTION,
    }
    base.update(overrides)
    return DecisionRecord(**base)


# ---------------------------------------------------------------------------
# ET-LC-006 — the decision payload is immutable
# ---------------------------------------------------------------------------


def test_decision_record_is_frozen():
    """ET-LC-006: attribute assignment on a stored decision raises."""
    record = _record()

    with pytest.raises(ValidationError):
        record.outcome = DecisionOutcome.REFUSED  # type: ignore[misc]


def test_store_refuses_to_overwrite(decision_store: InMemoryDecisionStore):
    """ET-LC-006: immutability is enforced at the persistence boundary too.

    A frozen model stops attribute assignment. Only the store stops a caller
    putting back a modified copy under the same identifier.
    """
    decision_store.append(_record("dec-1"))

    with pytest.raises(ImmutableRecordViolation, match="superseding record"):
        decision_store.append(_record("dec-1", latency_ms=999))


def test_supersession_creates_a_new_record_and_leaves_the_original(
    decision_store: InMemoryDecisionStore,
):
    """ET-LC-003 / ET-LC-006: supersession is recorded by the successor."""
    original = _record("dec-1")
    decision_store.append(original)

    successor = original.superseded_by(
        decision_id="dec-2",
        recorded_at=NOW,
        outcome=DecisionOutcome.REFUSED,
        strategy=None,
        reason_code=ReasonCode.UNSUPPORTED_CLAIM,
        verification_mechanism="scripted",
        claim_counts=ClaimCounts.not_measured(),
        evidence_count=1,
        latency_ms=15,
    )
    decision_store.append(successor)

    assert successor.supersedes == "dec-1"
    assert decision_store.get("dec-1") == original  # untouched
    assert decision_store.successors_of("dec-1") == (successor,)


def test_denied_request_records_no_evidence():
    """ET-AUTH-001: authorization precedes retrieval, so a denial read nothing."""
    with pytest.raises(ValidationError, match="zero evidence"):
        _record(
            authorization_result=AuthorizationResult.DENIED,
            outcome=DecisionOutcome.REFUSED,
            strategy=None,
            reason_code=ReasonCode.AUTHORIZATION_DENIED,
            evidence_count=3,
        )


def test_record_enforces_the_outcome_strategy_relation():
    """ET-OUT-002: a refused record carrying a strategy cannot be constructed."""
    with pytest.raises(ValidationError, match="ET-OUT-002"):
        _record(
            outcome=DecisionOutcome.REFUSED,
            strategy=ResponseStrategy.DIRECT,
            reason_code=ReasonCode.VERIFIER_ERROR,
        )


# ---------------------------------------------------------------------------
# ET-LC-001 / ET-LC-002 — acceptance and rejection require accountable review
# ---------------------------------------------------------------------------


def test_accept_requires_an_accountable_human(state_machine, system_actor):
    """ET-LC-001: a system actor cannot promote a decision record.

    This is what makes "an accountable human reviewed this" checkable rather
    than a sentence in a policy about oversight.
    """
    with pytest.raises(MissingAccountableReview, match="accountable human"):
        state_machine.accept("dec-1", reviewer=system_actor)


def test_accept_by_a_principal_succeeds(state_machine, architect):
    """ET-LC-001: an attributed principal with a role may accept."""
    transition = state_machine.accept("dec-1", reviewer=architect)

    assert transition.to_state is LifecycleState.ACCEPTED
    assert transition.actor.actor_id == "jordan-reyes"
    assert transition.actor.role == "architect"
    assert transition.reason_code is ReasonCode.REVIEW_ACCEPTED
    assert transition.contract_version == "1.0"
    assert state_machine.current_state("dec-1") is LifecycleState.ACCEPTED


def test_reject_requires_an_accountable_human(state_machine, system_actor):
    """ET-LC-002: rejection is a human act with attribution."""
    with pytest.raises(MissingAccountableReview):
        state_machine.reject("dec-1", reviewer=system_actor)


def test_rejected_records_are_retained(state_machine, architect):
    """ET-LC-002: a rejected record is retained so the path is not re-walked."""
    state_machine.reject("dec-1", reviewer=architect, note="duplicates an earlier decision")

    history = state_machine.history("dec-1")
    assert len(history) == 1
    assert history[0].to_state is LifecycleState.REJECTED
    assert history[0].note == "duplicates an earlier decision"


def test_transition_records_the_full_attribution(state_machine, architect):
    """ET-LC-001: actor, role, timestamp, reason code, and contract version."""
    t = state_machine.accept("dec-1", reviewer=architect)

    assert t.actor.actor_type is ActorType.PRINCIPAL
    assert t.recorded_at is not None
    assert t.reason_code is ReasonCode.REVIEW_ACCEPTED
    assert t.contract_id == "executable-trust-reference"
    assert t.sequence == 1


# ---------------------------------------------------------------------------
# ET-LC-003 — supersession
# ---------------------------------------------------------------------------


def test_supersede_requires_a_successor(state_machine, architect):
    """ET-LC-003: a supersession that names no successor records a dead end."""
    state_machine.accept("dec-1", reviewer=architect)

    with pytest.raises(InvalidTransition, match="successor"):
        state_machine.transition(
            "dec-1",
            LifecycleState.SUPERSEDED,
            actor=architect,
            reason_code=ReasonCode.SUPERSESSION_REPLACED,
        )


def test_supersede_links_to_the_successor(state_machine, architect):
    """ET-LC-003: the link is append-only and points forward."""
    state_machine.accept("dec-1", reviewer=architect)
    t = state_machine.supersede("dec-1", successor_decision_id="dec-2", actor=architect)

    assert t.to_state is LifecycleState.SUPERSEDED
    assert t.successor_decision_id == "dec-2"
    assert state_machine.current_state("dec-1") is LifecycleState.SUPERSEDED


# ---------------------------------------------------------------------------
# ET-LC-004 / ET-LC-005 — terminal states and undeclared transitions
# ---------------------------------------------------------------------------


def test_terminal_state_is_permanent(state_machine, architect):
    """ET-LC-004: nothing leaves REJECTED."""
    state_machine.reject("dec-1", reviewer=architect)

    with pytest.raises(InvalidTransition, match="terminal"):
        state_machine.accept("dec-1", reviewer=architect)


def test_superseded_is_also_terminal(state_machine, architect):
    """ET-LC-004: a superseded record is retained as recorded."""
    state_machine.accept("dec-1", reviewer=architect)
    state_machine.supersede("dec-1", successor_decision_id="dec-2", actor=architect)

    with pytest.raises(InvalidTransition, match="terminal"):
        state_machine.accept("dec-1", reviewer=architect)


def test_undeclared_transition_is_rejected(state_machine, architect):
    """ET-LC-005: PROPOSED -> SUPERSEDED is not declared and is refused."""
    with pytest.raises(InvalidTransition, match="not a declared transition"):
        state_machine.transition(
            "dec-1",
            LifecycleState.SUPERSEDED,
            actor=architect,
            reason_code=ReasonCode.SUPERSESSION_REPLACED,
            successor_decision_id="dec-2",
        )


# ---------------------------------------------------------------------------
# ET-LC-007 — current state is a projection
# ---------------------------------------------------------------------------


def test_initial_state_with_no_transitions(state_machine):
    """ET-LC-007: a record with no history sits in the initial state."""
    assert state_machine.current_state("never-seen") is LifecycleState.PROPOSED
    assert project_state(()) is LifecycleState.PROPOSED


def test_current_state_is_derived_not_stored(state_machine, architect):
    """ET-LC-007: state is a fold over the log, so there is no field to desync."""
    state_machine.accept("dec-1", reviewer=architect)
    state_machine.supersede("dec-1", successor_decision_id="dec-2", actor=architect)

    history = state_machine.history("dec-1")

    assert project_state(history) is LifecycleState.SUPERSEDED
    assert state_at(history, 1) is LifecycleState.ACCEPTED
    assert state_at(history, 0) is LifecycleState.PROPOSED


def test_history_is_append_only(state_machine, architect, transition_log):
    """ET-LC-007: a recorded position is never rewritten."""
    state_machine.accept("dec-1", reviewer=architect)
    replayed = transition_log.for_decision("dec-1")[0]

    with pytest.raises(ImmutableRecordViolation, match="append-only"):
        transition_log.append(replayed)


def test_sequences_are_contiguous(state_machine, architect, transition_log):
    """ET-LC-007: a gap would mean a lost transition and is caught when it happens."""
    state_machine.accept("dec-1", reviewer=architect)
    out_of_order = transition_log.for_decision("dec-1")[0].model_copy(
        update={"sequence": 5, "transition_id": "txn-5"}
    )

    with pytest.raises(ImmutableRecordViolation, match="out of order"):
        transition_log.append(out_of_order)


def test_system_actor_may_not_hold_a_role():
    """ET-LC-001: accountability belongs to principals, not processes."""
    with pytest.raises(ValidationError, match="must not declare a role"):
        Actor(actor_id="scheduler", actor_type=ActorType.SYSTEM, role="architect")


def test_principal_must_declare_a_role():
    """ET-LC-001: a principal with no role cannot be held accountable for anything."""
    with pytest.raises(ValidationError, match="must declare the role"):
        Actor(actor_id="someone", actor_type=ActorType.PRINCIPAL)
