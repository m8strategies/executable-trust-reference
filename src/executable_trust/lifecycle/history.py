"""Append-only transition history, and the state projection over it.

The log is the authority. Current state is *computed* by folding the ordered
transitions, never stored. That is what makes "current state is a projection of
append-only facts" true rather than aspirational: there is no field to
accidentally update, and no field that can disagree with the history.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from executable_trust.domain.enums import LifecycleState
from executable_trust.domain.errors import ImmutableRecordViolation
from executable_trust.lifecycle.models import LifecycleTransition


@runtime_checkable
class TransitionLog(Protocol):
    """Append-only storage for lifecycle transitions."""

    def append(self, transition: LifecycleTransition) -> None: ...

    def for_decision(self, decision_id: str) -> tuple[LifecycleTransition, ...]: ...

    def all(self) -> tuple[LifecycleTransition, ...]: ...


class InMemoryTransitionLog:
    """Reference adapter for the transition log.

    Enforces two structural properties on append:

    - a ``(decision_id, sequence)`` pair is unique, so history cannot be
      rewritten by re-recording a position;
    - sequences are contiguous from 1, so a gap — which would mean a lost
      transition — is caught when it happens rather than inferred later from a
      state that makes no sense.
    """

    def __init__(self) -> None:
        self._transitions: list[LifecycleTransition] = []
        self._seen: set[tuple[str, int]] = set()

    def append(self, transition: LifecycleTransition) -> None:
        key = (transition.decision_id, transition.sequence)
        if key in self._seen:
            raise ImmutableRecordViolation(
                f"transition {transition.sequence} for decision "
                f"{transition.decision_id!r} already exists; history is append-only "
                "and a recorded position is never rewritten"
            )
        expected = len(self.for_decision(transition.decision_id)) + 1
        if transition.sequence != expected:
            raise ImmutableRecordViolation(
                f"transition sequence {transition.sequence} is out of order for "
                f"decision {transition.decision_id!r}; expected {expected}"
            )
        self._seen.add(key)
        self._transitions.append(transition)

    def for_decision(self, decision_id: str) -> tuple[LifecycleTransition, ...]:
        """Transitions for one decision, ordered by sequence."""
        return tuple(
            sorted(
                (t for t in self._transitions if t.decision_id == decision_id),
                key=lambda t: t.sequence,
            )
        )

    def all(self) -> tuple[LifecycleTransition, ...]:
        return tuple(self._transitions)

    def __len__(self) -> int:
        return len(self._transitions)


def project_state(
    transitions: tuple[LifecycleTransition, ...],
    *,
    initial: LifecycleState = LifecycleState.PROPOSED,
) -> LifecycleState:
    """Fold an ordered transition history into the current state.

    With no transitions the record sits in its initial state. Otherwise the
    last transition's target wins, because every transition was validated
    against the contract before it was recorded.
    """
    if not transitions:
        return initial
    ordered = sorted(transitions, key=lambda t: t.sequence)
    return ordered[-1].to_state


def state_at(
    transitions: tuple[LifecycleTransition, ...],
    sequence: int,
    *,
    initial: LifecycleState = LifecycleState.PROPOSED,
) -> LifecycleState:
    """State as of a given sequence position.

    Reconstructing history is the reason the log exists. "What did this record
    look like when the decision was made?" is answerable from append-only facts
    rather than from memory.
    """
    return project_state(tuple(t for t in transitions if t.sequence <= sequence), initial=initial)
