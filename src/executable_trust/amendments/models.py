"""Amendment model.

An amendment is the Ratified property made concrete: a numbered, dated,
attributable change to a contract, recording what changed, why, what trade-off
is accepted, and what binds whoever implements the area next.

Three attribution roles are required and the author may not also be the
ratifier. Authorship is not ratification, and an amendment ratified by its own
author records a preference rather than a decision.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ContractAmendment(BaseModel):
    """A ratified change to a trust contract version."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    amendment_id: str = Field(pattern=r"^v\d+\.\d+-A\d+$")
    contract_id: str = Field(min_length=1)
    previous_contract_version: str = Field(pattern=r"^\d+\.\d+$")
    new_contract_version: str = Field(pattern=r"^\d+\.\d+$")

    title: str = Field(min_length=1)
    status: str = Field(min_length=1)

    author: str = Field(min_length=1)
    reviewer: str = Field(min_length=1)
    ratifier: str = Field(min_length=1)

    approved_at: datetime
    effective_from: datetime

    affected_rule_ids: tuple[str, ...] = Field(min_length=1)

    rationale: str = Field(min_length=1)
    accepted_trade_off: str = Field(min_length=1)
    forward_constraint: str | None = None
    compatibility_notes: str = Field(min_length=1)
    preserves_prior_version: bool

    @model_validator(mode="after")
    def _roles_are_distinct(self) -> ContractAmendment:
        if self.author == self.ratifier:
            raise ValueError(
                "an amendment's author may not also be its ratifier; authorship is not ratification"
            )
        return self

    @model_validator(mode="after")
    def _version_moves_forward(self) -> ContractAmendment:
        prev = tuple(int(p) for p in self.previous_contract_version.split("."))
        new = tuple(int(p) for p in self.new_contract_version.split("."))
        if new <= prev:
            raise ValueError(
                f"amendment moves from v{self.previous_contract_version} to "
                f"v{self.new_contract_version}, which is not forward"
            )
        return self

    @model_validator(mode="after")
    def _prior_version_is_preserved(self) -> ContractAmendment:
        if not self.preserves_prior_version:
            raise ValueError(
                "an amendment must preserve the contract version it amends; "
                "prior versions are retained, never rewritten"
            )
        return self

    @property
    def is_ratified(self) -> bool:
        return self.status == "ratified"
