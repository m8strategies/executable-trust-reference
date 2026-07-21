"""Deterministic identifiers and clocks.

Reproducibility is a property this repository claims, so it has to be built in
rather than hoped for. Two sources of nondeterminism would otherwise make every
baseline report differ from the last: random identifiers and the wall clock.

Both are therefore injected. :class:`IdFactory` produces stable, human-readable
identifiers from a seed, and :class:`FixedClock` returns a fixed instant. The
evaluation harness uses both, which is why running the baseline twice produces
byte-identical reports.

Production systems should inject a UUID factory and a real clock instead. The
protocols exist precisely so that substitution needs no change to any caller.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    """Source of the current time.

    Injected rather than called directly so that recorded timestamps are a
    decision of the composition root, not of every module that stamps one.
    """

    def now(self) -> datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        ...


class SystemClock:
    """Wall-clock time. The production default."""

    def now(self) -> datetime:
        return datetime.now(UTC)


class FixedClock:
    """A clock that advances only when told to.

    Used by tests and by the evaluation harness. ``tick`` exists so a sequence
    of events can carry increasing timestamps without reintroducing real time:
    ordering in this system is carried by explicit sequence numbers, but a
    monotonic timestamp still makes reports easier to read.
    """

    def __init__(
        self,
        start: datetime | None = None,
        *,
        step: timedelta = timedelta(seconds=1),
    ) -> None:
        self._now = start or datetime(2026, 1, 1, tzinfo=UTC)
        self._step = step

    def now(self) -> datetime:
        return self._now

    def tick(self) -> datetime:
        """Advance by one step and return the new time."""
        self._now = self._now + self._step
        return self._now


class IdFactory(Protocol):
    """Source of identifiers for records, events, and transitions."""

    def new_id(self, prefix: str) -> str:
        """Return a new identifier carrying ``prefix``."""
        ...


class SequentialIdFactory:
    """Deterministic identifiers of the form ``<prefix>-<seed>-<n>``.

    Counters are per prefix, so decision identifiers and telemetry event
    identifiers advance independently and adding a telemetry event does not
    shift every subsequent decision identifier. That property is what keeps a
    report diff readable when one case changes.
    """

    def __init__(self, seed: str = "ref") -> None:
        self._seed = seed
        self._counters: dict[str, int] = {}

    def new_id(self, prefix: str) -> str:
        nxt = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = nxt
        return f"{prefix}-{self._seed}-{nxt:04d}"

    def reset(self) -> None:
        """Clear all counters. Lets one process run several reproducible suites."""
        self._counters.clear()


class UuidIdFactory:
    """Random identifiers. The production default; never used in the baseline."""

    def new_id(self, prefix: str) -> str:
        return f"{prefix}-{uuid.uuid4()}"


def new_correlation_id(factory: IdFactory) -> str:
    """Return a correlation identifier for one request.

    A correlation identifier is generated at entry and travels with the
    request. It is either present or absent; it is never emitted as an empty
    string or a placeholder like ``"unknown"``, because a placeholder in a
    query result is indistinguishable from a real value that happens to say
    unknown.
    """
    return factory.new_id("corr")
