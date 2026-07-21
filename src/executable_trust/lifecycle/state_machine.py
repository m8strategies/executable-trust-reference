"""The lifecycle state machine (ET-LC-001..007).

The paper's approval workflow, made executable:

    *A generated decision record must be reviewed by an accountable human
    before it can inform future recommendations. Rejected alternatives are
    retained, not deleted.*

The design decision that matters is where the invalid transition is refused. A
hidden control in an interface is bypassed by anyone calling the API directly.
This machine refuses at the domain boundary **and** the log refuses at the
persistence boundary, so there is no path that records an undeclared
transition.

Transitions are read from the contract, not hardcoded. Adding a state to the
contract without adding it here fails loudly at validation rather than
silently permitting something nobody reviewed.
"""

from __future__ import annotations

from datetime import datetime

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import LifecycleState, ReasonCode
from executable_trust.domain.errors import InvalidTransition, MissingAccountableReview
from executable_trust.domain.identifiers import Clock, IdFactory
from executable_trust.domain.models import Actor
from executable_trust.lifecycle.history import InMemoryTransitionLog, project_state
from executable_trust.lifecycle.models import LifecycleTransition


class LifecycleStateMachine:
    """Validates and records decision-record lifecycle transitions."""

    def __init__(
        self,
        contract: TrustContract,
        log: InMemoryTransitionLog,
        *,
        clock: Clock,
        ids: IdFactory,
    ) -> None:
        self._contract = contract
        self._log = log
        self._clock = clock
        self._ids = ids

    # -- queries -----------------------------------------------------------

    def current_state(self, decision_id: str) -> LifecycleState:
        """Derived from the log. There is no stored current-state field."""
        return project_state(
            self._log.for_decision(decision_id),
            initial=self._contract.lifecycle.initial_state,
        )

    def history(self, decision_id: str) -> tuple[LifecycleTransition, ...]:
        return self._log.for_decision(decision_id)

    # -- the transition ----------------------------------------------------

    def transition(
        self,
        decision_id: str,
        to_state: LifecycleState,
        *,
        actor: Actor,
        reason_code: ReasonCode,
        successor_decision_id: str | None = None,
        note: str | None = None,
    ) -> LifecycleTransition:
        """Validate and record a transition.

        Raises:
            InvalidTransition: the transition is not declared by the contract,
                or it leaves a terminal state.
            MissingAccountableReview: the transition requires an attributable
                human review and did not receive one.
        """
        from_state = self.current_state(decision_id)
        lifecycle = self._contract.lifecycle

        # A terminal state is permanent. Checked before the transition lookup so
        # the error names the real problem rather than "undeclared transition".
        if from_state in lifecycle.terminal_states:
            raise InvalidTransition(
                f"decision {decision_id!r} is in terminal state {from_state.value}; "
                "terminal states are permanent (ET-LC-004). Revisiting the question "
                "creates a new record that may cite this one."
            )

        rule = self._contract.transition_rule(from_state, to_state)
        if rule is None:
            declared = sorted(f"{t.from_.value}->{t.to.value}" for t in lifecycle.transitions)
            raise InvalidTransition(
                f"{from_state.value} -> {to_state.value} is not a declared transition "
                f"for decision {decision_id!r} (ET-LC-005); declared: {declared}"
            )

        if rule.requires_human_review and not actor.is_accountable_human:
            raise MissingAccountableReview(
                f"transition {rule.id} ({from_state.value} -> {to_state.value}) requires "
                "an attributable review by an accountable human; the supplied actor is "
                f"{actor.actor_type.value} with role {actor.role!r}. A promotion without "
                "an accountable reviewer is rejected at the boundary, not hidden in a UI."
            )

        if rule.requires_role and not actor.role:
            raise MissingAccountableReview(
                f"transition {rule.id} requires the acting role to be recorded"
            )

        if rule.requires_successor and not successor_decision_id:
            raise InvalidTransition(
                f"transition {rule.id} requires the successor decision to be named "
                "(ET-LC-003); supersession is recorded by reference to the successor"
            )

        transition = LifecycleTransition(
            transition_id=self._ids.new_id("txn"),
            decision_id=decision_id,
            sequence=len(self._log.for_decision(decision_id)) + 1,
            from_state=from_state,
            to_state=to_state,
            actor=actor,
            reason_code=reason_code,
            recorded_at=_now(self._clock),
            contract_id=self._contract.contract_id,
            contract_version=self._contract.version,
            successor_decision_id=successor_decision_id,
            note=note,
        )
        self._log.append(transition)
        return transition

    # -- convenience wrappers ---------------------------------------------

    def accept(
        self, decision_id: str, *, reviewer: Actor, note: str | None = None
    ) -> LifecycleTransition:
        """Record an accountable human's acceptance (ET-LC-001)."""
        return self.transition(
            decision_id,
            LifecycleState.ACCEPTED,
            actor=reviewer,
            reason_code=ReasonCode.REVIEW_ACCEPTED,
            note=note,
        )

    def reject(
        self, decision_id: str, *, reviewer: Actor, note: str | None = None
    ) -> LifecycleTransition:
        """Record an accountable human's rejection (ET-LC-002).

        The record is retained, never deleted, so the organization can detect
        when it is about to repeat a path it already evaluated and declined.
        """
        return self.transition(
            decision_id,
            LifecycleState.REJECTED,
            actor=reviewer,
            reason_code=ReasonCode.REVIEW_REJECTED,
            note=note,
        )

    def supersede(
        self,
        decision_id: str,
        *,
        successor_decision_id: str,
        actor: Actor,
        note: str | None = None,
    ) -> LifecycleTransition:
        """Record supersession by a newer decision (ET-LC-003)."""
        return self.transition(
            decision_id,
            LifecycleState.SUPERSEDED,
            actor=actor,
            reason_code=ReasonCode.SUPERSESSION_REPLACED,
            successor_decision_id=successor_decision_id,
            note=note,
        )


def _now(clock: Clock) -> datetime:
    return clock.now()
