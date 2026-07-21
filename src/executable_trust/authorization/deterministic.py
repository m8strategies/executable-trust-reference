"""Deterministic, deny-by-default authorizer.

No network, no directory, no credentials. Given the same actor and resource it
returns the same decision every time, which is what lets the evaluation
baseline be reproducible.
"""

from __future__ import annotations

from executable_trust.authorization.policy import REFERENCE_POLICY, AuthorizationPolicy
from executable_trust.authorization.protocol import AuthorizationDecision
from executable_trust.domain.enums import ActorType
from executable_trust.domain.models import Actor


class DeterministicAuthorizer:
    """Evaluates an :class:`AuthorizationPolicy` with no side effects.

    Four denial paths, kept distinct in the reason text because "who are you",
    "you have no grants", and "that resource is not yours" are different
    operational problems even though all three deny.
    """

    def __init__(self, policy: AuthorizationPolicy = REFERENCE_POLICY) -> None:
        self._policy = policy

    @property
    def policy(self) -> AuthorizationPolicy:
        return self._policy

    def authorize(self, actor: Actor, resource: str) -> AuthorizationDecision:
        label = f"{self._policy.policy_id}@{self._policy.version}"

        # A system actor holds no role and therefore no grant. Governed reads
        # are performed on behalf of an accountable principal or not at all.
        if actor.actor_type is not ActorType.PRINCIPAL:
            return AuthorizationDecision.deny(
                f"{label}: actor {actor.actor_id!r} is a system actor and holds no role grant"
            )

        role = actor.role
        if not role:
            return AuthorizationDecision.deny(f"{label}: actor {actor.actor_id!r} declares no role")

        grant = self._policy.grant_for(role)
        if grant is None:
            return AuthorizationDecision.deny(
                f"{label}: role {role!r} is not recognised by the policy"
            )

        if not grant.permits(resource):
            return AuthorizationDecision.deny(
                f"{label}: role {role!r} is not granted access to resource {resource!r}"
            )

        return AuthorizationDecision.allow(f"{label}: role {role!r} is granted {resource!r}")
