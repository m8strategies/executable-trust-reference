"""Value types for the governed request path.

Separated from :mod:`executable_trust.decisions.service` so that a caller can
depend on the *shape* of a governed result without importing the orchestrator
and everything it wires together.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from executable_trust.authorization.protocol import AuthorizationDecision
from executable_trust.decisions.records import DecisionRecord
from executable_trust.domain.enums import EvidenceQuality
from executable_trust.evidence.models import EvidenceSet
from executable_trust.verification.models import VerificationDecision

#: A generator takes the question and the evidence window and returns a
#: candidate answer. Deliberately the narrowest possible signature: this
#: repository is not about generation, it is about what surrounds it.
Generator = Callable[[str, EvidenceSet], str]


@dataclass(frozen=True)
class GovernedResult:
    """Everything one governed request produced.

    ``generation_invoked`` is carried explicitly rather than inferred. "The
    generator was never called" is a property the tests must assert directly;
    inferring it from an empty answer would pass for the wrong reason if a
    generator ever returned an empty string.

    ``telemetry_captured`` is likewise explicit, and a ``False`` here is not an
    error: capture fails open, so a failed capture leaves the decision above it
    completely unchanged.
    """

    decision: VerificationDecision
    record: DecisionRecord
    authorization: AuthorizationDecision
    evidence_quality: EvidenceQuality | None
    generation_invoked: bool
    telemetry_captured: bool
