"""The authorization seam.

Authorization is enforced at the perimeter, before retrieval and before
generation. Modelling it as a Protocol means the reference implementation ships
a deterministic policy evaluator while a real deployment substitutes an
identity provider or a policy engine, and no caller changes.

The decision is a value, not an exception. A denial is a governed outcome that
gets recorded with a reason code like any other refusal — it is not an error
condition to be caught somewhere up the stack.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from executable_trust.domain.enums import AuthorizationResult
from executable_trust.domain.models import Actor


class AuthorizationDecision(BaseModel):
    """The result of one authorization check."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    result: AuthorizationResult
    reason: str = Field(min_length=1)

    @property
    def allowed(self) -> bool:
        return self.result is AuthorizationResult.ALLOWED

    @classmethod
    def allow(cls, reason: str = "policy grants access") -> AuthorizationDecision:
        return cls(result=AuthorizationResult.ALLOWED, reason=reason)

    @classmethod
    def deny(cls, reason: str) -> AuthorizationDecision:
        return cls(result=AuthorizationResult.DENIED, reason=reason)


@runtime_checkable
class Authorizer(Protocol):
    """Decides whether an actor may access a resource.

    Implementations must be deny-by-default: an actor, role, or resource the
    policy does not recognise is denied rather than permitted. A policy that
    fails open is not an access control.
    """

    def authorize(self, actor: Actor, resource: str) -> AuthorizationDecision:
        """Return the authorization decision for ``actor`` against ``resource``."""
        ...
