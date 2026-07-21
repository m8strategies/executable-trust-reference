"""Evidence models.

An evidence item is something retrieved for *this* request. That qualifier is
the whole point: a claim is checked against what the system actually retrieved,
never against general world knowledge and never against what sounds right.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from executable_trust.domain.enums import EvidenceQuality


class EvidenceItem(BaseModel):
    """One retrieved passage, with its relevance and its origin.

    ``provenance`` is required and has no default. Evidence whose origin is
    unknown is not evidence: an answer verified against an ungoverned corpus is
    a precise measurement of an unknown quantity.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    relevance_score: float = Field(ge=0.0, le=1.0)
    provenance: str = Field(min_length=1)


class EvidenceSet(BaseModel):
    """The evidence retrieved for one request, in ranked order."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    evidence_set_ref: str = Field(min_length=1)
    items: tuple[EvidenceItem, ...] = ()

    @property
    def count(self) -> int:
        return len(self.items)

    @property
    def top_score(self) -> float:
        """Highest relevance score, or 0.0 when the set is empty."""
        return max((i.relevance_score for i in self.items), default=0.0)

    def truncated_to(self, top_k: int) -> EvidenceSet:
        """Return the top ``top_k`` items by relevance, ties broken by identifier.

        Deterministic ordering matters: an unstable sort would make the same
        request produce different evidence windows across runs, and a
        reproducible baseline would be impossible.
        """
        ranked = sorted(self.items, key=lambda i: (-i.relevance_score, i.evidence_id))
        return EvidenceSet(evidence_set_ref=self.evidence_set_ref, items=tuple(ranked[:top_k]))


class GateResult(BaseModel):
    """The outcome of the evidence-sufficiency check.

    Carries the observed values alongside the verdict so a refusal can be
    explained without re-running the gate: "0.21 against a bar of 0.35" is
    actionable, "insufficient evidence" alone is not.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    sufficient: bool
    quality: EvidenceQuality
    observed_top_score: float
    observed_count: int
    threshold_score: float
    threshold_count: int
    detail: str = Field(min_length=1)
