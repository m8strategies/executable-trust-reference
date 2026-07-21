"""Evidence sufficiency, enforced before generation (ET-EV-001, ET-EV-002).

This is the paper's ``RETRIEVAL_GATE`` made literal. Two properties matter more
than the arithmetic:

**The refusal is pre-generation.** When the gate fails, the generator is never
invoked. Generation that never happens cannot be trusted incorrectly, and
refusing early is cheaper than generating an answer and discarding it.

**The thresholds are contract configuration, not constants.** The people
accountable for the evidence bar can see and change the number without a code
change. That is itself a trust property: a threshold buried in source is a
threshold nobody reviews.
"""

from __future__ import annotations

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import EvidenceQuality
from executable_trust.evidence.models import EvidenceSet, GateResult


def check_provenance(evidence: EvidenceSet, contract: TrustContract) -> str | None:
    """Return a failure detail if any item's provenance is unacceptable.

    Runs before the sufficiency gate. A high-scoring passage from an
    unrecognised source is worse than no passage at all: it would pass the
    relevance bar and carry unknown authority.
    """
    rule = contract.evidence.provenance
    if not rule.required:
        return None

    permitted = set(rule.permitted_sources)
    for item in evidence.items:
        if item.provenance not in permitted:
            return (
                f"evidence item {item.evidence_id!r} declares provenance "
                f"{item.provenance!r}, which is not in the permitted set "
                f"{sorted(permitted)}"
            )
    return None


def evaluate_gate(evidence: EvidenceSet, contract: TrustContract) -> GateResult:
    """Apply the contract's evidence gate to a retrieved set.

    ``EMPTY`` is reported distinctly from ``INSUFFICIENT``. Both refuse under
    the same reason code, but "retrieval found nothing" and "retrieval found
    something too weak" are different operational problems, and collapsing them
    hides which one is happening.
    """
    gate = contract.evidence.gate
    window = evidence.truncated_to(gate.top_k)
    count = window.count
    top = window.top_score

    if count == 0:
        return GateResult(
            sufficient=False,
            quality=EvidenceQuality.EMPTY,
            observed_top_score=0.0,
            observed_count=0,
            threshold_score=gate.min_similarity_score,
            threshold_count=gate.min_chunks_required,
            detail="retrieval returned no evidence items",
        )

    if count < gate.min_chunks_required:
        return GateResult(
            sufficient=False,
            quality=EvidenceQuality.INSUFFICIENT,
            observed_top_score=top,
            observed_count=count,
            threshold_score=gate.min_similarity_score,
            threshold_count=gate.min_chunks_required,
            detail=(
                f"retrieved {count} evidence item(s); the contract requires at "
                f"least {gate.min_chunks_required}"
            ),
        )

    if top < gate.min_similarity_score:
        return GateResult(
            sufficient=False,
            quality=EvidenceQuality.INSUFFICIENT,
            observed_top_score=top,
            observed_count=count,
            threshold_score=gate.min_similarity_score,
            threshold_count=gate.min_chunks_required,
            detail=(
                f"top relevance score {top:.3f} is below the contract bar of "
                f"{gate.min_similarity_score:.3f}"
            ),
        )

    return GateResult(
        sufficient=True,
        quality=EvidenceQuality.SUFFICIENT,
        observed_top_score=top,
        observed_count=count,
        threshold_score=gate.min_similarity_score,
        threshold_count=gate.min_chunks_required,
        detail=(
            f"{count} evidence item(s) with top relevance {top:.3f} clear the "
            f"contract bar of {gate.min_similarity_score:.3f}"
        ),
    )
