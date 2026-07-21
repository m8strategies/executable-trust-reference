"""Telemetry storage.

A narrow Protocol, an in-memory adapter, and — importantly — a store that
always fails. The failing store is not a test double bolted on later; it is
part of the reference implementation, because "telemetry capture never breaks
the decision it describes" is only credible if the repository ships a way to
prove it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from executable_trust.domain.enums import Environment, Population
from executable_trust.telemetry.events import TelemetryEvent


@runtime_checkable
class TelemetryStore(Protocol):
    """Append-only storage for telemetry events."""

    def append(self, event: TelemetryEvent) -> None: ...

    def all(self) -> tuple[TelemetryEvent, ...]: ...


class InMemoryTelemetryStore:
    """Reference adapter. Append-only, insertion-ordered."""

    def __init__(self) -> None:
        self._events: list[TelemetryEvent] = []

    def append(self, event: TelemetryEvent) -> None:
        self._events.append(event)

    def all(self) -> tuple[TelemetryEvent, ...]:
        return tuple(self._events)

    def filtered(
        self,
        *,
        environments: tuple[Environment, ...] | None = None,
        population: Population | None = None,
    ) -> tuple[TelemetryEvent, ...]:
        """Events matching a population filter.

        The metrics layer uses this to build observed metrics. Filtering at the
        query rather than trusting the caller to remember is what keeps test
        traffic out of a number described as production behaviour.
        """
        events = self._events
        if environments is not None:
            allowed = set(environments)
            events = [e for e in events if e.environment in allowed]
        if population is not None:
            events = [e for e in events if e.population is population]
        return tuple(events)

    def __len__(self) -> int:
        return len(self._events)


class AlwaysFailingTelemetryStore:
    """A store that raises on every write.

    Ships in the package rather than in the tests because the fail-open
    property is an architectural claim, and a claim the repository cannot
    demonstrate on demand is a claim nobody should believe. Wiring this store
    into the reference flow must leave every governed decision byte-identical.
    """

    class Failure(RuntimeError):
        """Raised on every append."""

    def append(self, event: TelemetryEvent) -> None:
        raise self.Failure(
            "simulated telemetry backend failure (the governed decision must be unaffected)"
        )

    def all(self) -> tuple[TelemetryEvent, ...]:
        return ()
