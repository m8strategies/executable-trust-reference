"""The verification seam.

The narrow interface that makes the enforcement mechanism swappable. Everything
upstream depends on this Protocol and on nothing beneath it: no model client,
no NLI library, no prompt. A verifier that requires rewriting its callers to
replace will never be replaced, and a verification engine that cannot be
replaced cannot be improved.

Two obligations on every implementation:

1. **Fail closed.** On any internal error, raise
   :class:`~executable_trust.domain.errors.VerifierFailure` with the reason
   code describing the fault. Never return a response that would read as
   verified.
2. **Declare provenance.** ``name`` identifies the mechanism and is recorded on
   every decision, so a decision can always be attributed to the verifier that
   made it — including after the verifier has been replaced.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from executable_trust.evidence.models import EvidenceSet
from executable_trust.verification.models import VerifierResponse


@runtime_checkable
class Verifier(Protocol):
    """Decomposes a candidate answer into claims and classifies each one."""

    @property
    def name(self) -> str:
        """Stable mechanism identifier, recorded on every decision."""
        ...

    def verify(
        self,
        answer: str,
        evidence: EvidenceSet,
        question: str,
    ) -> VerifierResponse:
        """Return claim verdicts for ``answer`` against ``evidence``.

        Implementations must classify each claim strictly against the supplied
        evidence — not general world knowledge, and not plausibility.

        Raises:
            VerifierFailure: on any internal fault, including timeout and
                unavailability. Never returns a partial or optimistic result.
        """
        ...


@runtime_checkable
class HealthReporting(Protocol):
    """Optional capability: a verifier that reports its own health.

    Separate from :class:`Verifier` so that implementing health is not a
    precondition for implementing verification. The circuit breaker treats a
    verifier without this capability as healthy until it observes a fault.
    """

    @property
    def healthy(self) -> bool:
        """False when the mechanism knows it cannot currently be relied on."""
        ...
