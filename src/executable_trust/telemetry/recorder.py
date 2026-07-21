"""Fail-open telemetry capture (ET-TEL-001).

The inverse discipline of the enforcement rule, and the inversion is the whole
design:

- **Verification fails closed.** On any error it refuses. Lost answers are
  acceptable; an unverified answer is not.
- **Telemetry fails open.** On any error it logs and continues. Lost telemetry
  is acceptable; a blocked answer is not.

Reversing either direction is a design defect. A verifier that fails open is a
false sense of safety; a telemetry write that can break a governed decision has
made the observer more important than the thing observed.

The entire capture path is wrapped. A bare ``except Exception`` is normally a
smell — here it is the requirement, because the caller must not care what went
wrong. The exception is logged at warning level with its type, never re-raised,
and never surfaced to the consumer.
"""

from __future__ import annotations

import logging
from typing import Any

from executable_trust.decisions.records import DecisionRecord
from executable_trust.domain.enums import Environment, EvidenceQuality, Population
from executable_trust.domain.identifiers import Clock, IdFactory
from executable_trust.telemetry.events import TelemetryEvent

logger = logging.getLogger(__name__)


class TelemetryRecorder:
    """Captures decisions to a telemetry store, never breaking the caller."""

    def __init__(
        self,
        store: Any,
        *,
        clock: Clock,
        ids: IdFactory,
        environment: Environment,
        population: Population,
    ) -> None:
        self._store = store
        self._clock = clock
        self._ids = ids
        self._environment = environment
        self._population = population
        self._failures = 0

    @property
    def capture_failures(self) -> int:
        """How many captures have failed.

        Exposed so an operator can alarm on capture health. A fail-open path
        that is silent about failing is indistinguishable from one that is
        working, and "we have telemetry" would then be unfalsifiable.
        """
        return self._failures

    def record(
        self,
        decision: DecisionRecord,
        *,
        evidence_quality: EvidenceQuality | None = None,
    ) -> TelemetryEvent | None:
        """Capture one decision. Returns the event, or ``None`` if capture failed.

        Never raises. The return value is informational: a caller that ignores
        it behaves correctly, which is the point — capture is not on the
        critical path and must not look like it is.
        """
        try:
            event = TelemetryEvent(
                event_id=self._ids.new_id("evt"),
                captured_at=self._clock.now(),
                decision_id=decision.decision_id,
                correlation_id=decision.correlation_id,
                outcome=decision.outcome,
                strategy=decision.strategy,
                reason_code=decision.reason_code,
                verification_mechanism=decision.verification_mechanism,
                evidence_count=decision.evidence_count,
                evidence_quality=evidence_quality,
                claim_counts=decision.claim_counts,
                latency_ms=decision.latency_ms,
                contract_id=decision.contract_id,
                contract_version=decision.contract_version,
                environment=self._environment,
                population=self._population,
            )
            self._store.append(event)
        except Exception as exc:
            self._failures += 1
            logger.warning(
                "telemetry capture failed (fail-open, governed decision unaffected): %s: %s",
                type(exc).__name__,
                exc,
            )
            return None
        return event
