"""Synthetic authorization policy.

Every actor, role, and resource in this module is invented for the reference
implementation. There is no directory, no identity provider, and no real
principal anywhere in this repository.

The policy shape is role-based and deny-by-default: a role grants access to an
explicit set of resource patterns, and anything not granted is denied. Wildcards
are supported only as a trailing ``*`` segment, deliberately — a policy language
rich enough to be interesting is a policy language rich enough to be wrong in
ways nobody notices.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class RoleGrant(BaseModel):
    """Resources one role may read."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    role: str = Field(min_length=1)
    resources: tuple[str, ...]

    def permits(self, resource: str) -> bool:
        return any(_matches(pattern, resource) for pattern in self.resources)


class AuthorizationPolicy(BaseModel):
    """A named, versioned set of role grants.

    Carries an identifier and a version because an authorization decision that
    cannot name the policy that produced it is not auditable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    grants: tuple[RoleGrant, ...]

    def grant_for(self, role: str) -> RoleGrant | None:
        for g in self.grants:
            if g.role == role:
                return g
        return None


def _matches(pattern: str, resource: str) -> bool:
    """Match a resource against a pattern with an optional trailing ``*``.

    ``handbook/*`` matches ``handbook/anything`` but not ``handbook`` itself,
    because a grant on a collection's contents is not a grant on the collection
    record.
    """
    if pattern == resource:
        return True
    if pattern.endswith("*"):
        prefix = pattern[:-1]
        return resource.startswith(prefix) and len(resource) > len(prefix)
    return False


#: The policy used by the examples, tests, and the synthetic golden set.
#:
#: SYNTHETIC: the roles and resources below describe a fictional company's
#: internal engineering handbook. They correspond to no real organization.
REFERENCE_POLICY = AuthorizationPolicy(
    policy_id="reference-role-policy",
    version="1.0",
    grants=(
        RoleGrant(
            role="engineer",
            resources=("handbook/*", "service-catalog/*"),
        ),
        RoleGrant(
            role="architect",
            resources=("handbook/*", "service-catalog/*", "architecture-standards/*"),
        ),
        RoleGrant(
            role="operations",
            resources=("handbook/*", "operational-policies/*", "change-management/*"),
        ),
        RoleGrant(
            role="auditor",
            resources=(
                "handbook/*",
                "service-catalog/*",
                "architecture-standards/*",
                "operational-policies/*",
                "change-management/*",
            ),
        ),
        # A role with no grants at all. Present so the deny path is exercised by
        # a role that legitimately exists, not only by an unknown one: those are
        # different failures and both must deny.
        RoleGrant(role="contractor", resources=()),
    ),
)
