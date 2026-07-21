"""Lifecycle transition model.

One entry in a decision record's append-only history. Attribution lives on the
transition rather than on the record, so who decided what, when, and under
which contract version survives independently of the record's content.

Ordering authority is :attr:`LifecycleTransition.sequence`, not the timestamp.
Two transitions recorded inside the same clock tick still have a defined order,
and a clock that jumps cannot reorder history.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import ActorType, LifecycleState, ReasonCode
from executable_trust.domain.models import Actor


class LifecycleTransition(BaseModel):
    """An append-only record of one state change."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    transition_id: str = Field(min_length=1)
    decision_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)

    from_state: LifecycleState | None = None
    to_state: LifecycleState

    actor: Actor
    reason_code: ReasonCode
    recorded_at: datetime

    contract_id: str = Field(min_length=1)
    contract_version: str = Field(pattern=r"^\d+\.\d+$")

    successor_decision_id: str | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _supersession_names_successor(self) -> LifecycleTransition:
        """A supersession that does not name its successor records a dead end."""
        if self.to_state is LifecycleState.SUPERSEDED and not self.successor_decision_id:
            raise ValueError(
                "a transition to SUPERSEDED must name the successor decision (ET-LC-003)"
            )
        if self.to_state is not LifecycleState.SUPERSEDED and self.successor_decision_id:
            raise ValueError(
                f"a transition to {self.to_state.value} must not name a successor decision"
            )
        return self

    @model_validator(mode="after")
    def _human_acts_are_attributed(self) -> LifecycleTransition:
        """Acceptance and rejection require an accountable principal.

        A system actor can never satisfy this. That is the whole point: it is
        what makes "an accountable human reviewed this" a checkable fact rather
        than a sentence in a policy about oversight.
        """
        if self.to_state in {LifecycleState.ACCEPTED, LifecycleState.REJECTED}:
            if self.actor.actor_type is not ActorType.PRINCIPAL:
                raise ValueError(
                    f"a transition to {self.to_state.value} requires an accountable "
                    "human reviewer; a system actor cannot accept or reject "
                    "(ET-LC-001 / ET-LC-002)"
                )
            if not self.actor.role:
                raise ValueError(
                    f"a transition to {self.to_state.value} requires the reviewer's role"
                )
        return self
