"""Shared domain models.

Framework-independent: these types know nothing about storage, transport, or
any model provider. Everything below is a Pydantic v2 model with
``model_config = ConfigDict(frozen=True, extra="forbid")``, for two reasons.

``frozen=True``
    Immutability is a contract requirement, not a style preference. A decision
    record that can be edited in place is a decision record whose history
    cannot be trusted.

``extra="forbid"``
    An unexpected field is a defect, not a convenience. Silently accepting one
    is how a field that means two different things gets introduced.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from executable_trust.domain.enums import ActorType, ClaimVerdict


class _Frozen(BaseModel):
    """Base for every immutable domain model."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class Claim(_Frozen):
    """One decomposed statement from a candidate answer, with its verdict.

    A ``Claim`` only exists once a verdict has been established. Verifier
    output that omits a verdict, or supplies one outside the controlled
    vocabulary, never becomes a ``Claim``: it fails closed during parsing. That
    is deliberate — an object that can exist without a verdict invites a
    ``getattr(claim, "verdict", SUPPORTED)`` somewhere downstream.
    """

    text: str = Field(min_length=1)
    verdict: ClaimVerdict
    evidence_ref: str | None = None
    states_scope_limitation: bool = False

    @model_validator(mode="after")
    def _supported_claims_may_cite_evidence(self) -> Claim:
        """An unsupported or contradicted claim must not cite supporting evidence.

        Citing evidence for a claim the evidence does not support is a
        contradiction in terms, and it would let a reader of the record believe
        a rejected claim was sourced.
        """
        if self.verdict is not ClaimVerdict.SUPPORTED and self.evidence_ref is not None:
            raise ValueError(
                f"a {self.verdict.value} claim must not carry evidence_ref; "
                "only a SUPPORTED claim is entailed by an evidence item"
            )
        return self


class ClaimCounts(_Frozen):
    """Counts of claims by verdict, as recorded on a decision and its telemetry.

    ``total is None`` and ``total == 0`` mean different things, and the
    distinction is load-bearing:

    - ``None`` — verification never ran (the request refused before reaching
      it, for example on authorization or evidence sufficiency).
    - ``0`` — verification ran and decomposed the answer into zero claims,
      which is itself a fail-closed refusal.

    Collapsing the two would make "we never checked" indistinguishable from "we
    checked and found nothing", which is precisely the confusion that lets an
    unverified answer be counted as a verified one.
    """

    total: int | None = None
    supported: int | None = None
    unsupported: int | None = None
    contradicted: int | None = None

    @classmethod
    def not_measured(cls) -> ClaimCounts:
        """Counts for a decision that refused before verification ran."""
        return cls()

    @classmethod
    def from_claims(cls, claims: tuple[Claim, ...]) -> ClaimCounts:
        """Counts for a decision where verification ran, even if it found nothing."""
        return cls(
            total=len(claims),
            supported=sum(1 for c in claims if c.verdict is ClaimVerdict.SUPPORTED),
            unsupported=sum(1 for c in claims if c.verdict is ClaimVerdict.UNSUPPORTED),
            contradicted=sum(1 for c in claims if c.verdict is ClaimVerdict.CONTRADICTED),
        )

    @property
    def measured(self) -> bool:
        """True when verification ran, regardless of what it found."""
        return self.total is not None


class Actor(_Frozen):
    """Who performed an act, and in what capacity.

    ``role`` is required for a principal and forbidden for a system actor. A
    system process does not hold an accountable role, and allowing it to claim
    one would make "an accountable human reviewed this" unverifiable.
    """

    actor_id: str = Field(min_length=1)
    actor_type: ActorType
    role: str | None = None

    @model_validator(mode="after")
    def _role_matches_actor_type(self) -> Actor:
        if self.actor_type is ActorType.PRINCIPAL and not self.role:
            raise ValueError("a principal actor must declare the role it is acting in")
        if self.actor_type is ActorType.SYSTEM and self.role:
            raise ValueError(
                "a system actor must not declare a role; accountability belongs to principals"
            )
        return self

    @property
    def is_accountable_human(self) -> bool:
        """True when this actor can satisfy a human-review requirement."""
        return self.actor_type is ActorType.PRINCIPAL and bool(self.role)


class TrustRequest(_Frozen):
    """One request entering the trust perimeter.

    Carries the correlation identifier from the gateway inward so that a
    decision, its telemetry, and its lifecycle history can all be joined after
    the fact without reconstructing anything.
    """

    correlation_id: str = Field(min_length=1)
    actor: Actor
    resource: str = Field(min_length=1)
    question: str = Field(min_length=1)
    contract_id: str = Field(min_length=1)
    contract_version: str = Field(pattern=r"^\d+\.\d+$")
