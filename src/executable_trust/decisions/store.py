"""Decision record persistence.

A narrow Protocol plus an in-memory adapter. Real deployments substitute a
database; the point of the seam is that the append-only guarantee is expressed
here, at the boundary, rather than being a property people remember to
preserve.

The store refuses overwrites. That refusal is what makes "records are immutable"
enforceable against a caller that holds a record and tries to put a modified
copy back — the frozen model stops attribute assignment, and the store stops
replacement.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from executable_trust.decisions.records import DecisionRecord
from executable_trust.domain.errors import ImmutableRecordViolation


@runtime_checkable
class DecisionStore(Protocol):
    """Append-only storage for decision records."""

    def append(self, record: DecisionRecord) -> None:
        """Store a new record.

        Raises:
            ImmutableRecordViolation: if the identifier already exists.
        """
        ...

    def get(self, decision_id: str) -> DecisionRecord | None:
        """Return the record, or ``None``."""
        ...

    def all(self) -> tuple[DecisionRecord, ...]:
        """Every record, in insertion order."""
        ...


class InMemoryDecisionStore:
    """Reference adapter. Append-only, insertion-ordered, no external services."""

    def __init__(self) -> None:
        self._records: dict[str, DecisionRecord] = {}

    def append(self, record: DecisionRecord) -> None:
        existing = self._records.get(record.decision_id)
        if existing is not None:
            raise ImmutableRecordViolation(
                f"decision {record.decision_id!r} already exists and cannot be replaced; "
                "corrections create a superseding record, never an overwrite"
            )
        self._records[record.decision_id] = record

    def get(self, decision_id: str) -> DecisionRecord | None:
        return self._records.get(decision_id)

    def all(self) -> tuple[DecisionRecord, ...]:
        return tuple(self._records.values())

    def successors_of(self, decision_id: str) -> tuple[DecisionRecord, ...]:
        """Records that cite ``decision_id`` as their predecessor."""
        return tuple(r for r in self._records.values() if r.supersedes == decision_id)

    def __len__(self) -> int:
        return len(self._records)
