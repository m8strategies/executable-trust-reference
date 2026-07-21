"""Evidence models and the sufficiency gate enforced before generation."""

from executable_trust.evidence.gate import check_provenance, evaluate_gate
from executable_trust.evidence.models import EvidenceItem, EvidenceSet, GateResult

__all__ = [
    "EvidenceItem",
    "EvidenceSet",
    "GateResult",
    "check_provenance",
    "evaluate_gate",
]
