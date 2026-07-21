"""Verification dependency health and the circuit breaker (ET-RES-001/002).

The paper's resilience policy, made executable:

    *If a downstream verification dependency degrades, the system degrades
    gracefully. It never skips verification to keep answering.*

Teams get this backwards under production pressure. When a dependency is
unhealthy the tempting fix is bypassing it so the user experience holds. The
breaker here is allowed to make the system slower or more conservative. It is
never allowed to make the system less verified — the only permitted outcomes
are *escalate* and *refuse*.

**Evidence note.** This mechanism is specified by the paper and implemented
here. It is not a component whose production behaviour the paper reports field
observations for. See ``docs/production-reference-boundary.md``.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.errors import VerifierFailure, VerifierUnavailable
from executable_trust.evidence.models import EvidenceSet
from executable_trust.verification.models import VerifierResponse


@dataclass
class HealthWindow:
    """A bounded rolling window of outcomes for one mechanism.

    Bounded because an unbounded fault history would let a mechanism that
    failed badly a month ago stay tripped forever, and would let a mechanism
    with a long clean history absorb a current outage without tripping.
    """

    capacity: int = 50
    _outcomes: deque[bool] = field(default_factory=deque, init=False, repr=False)

    def __post_init__(self) -> None:
        self._outcomes = deque(maxlen=self.capacity)

    def record(self, *, faulted: bool) -> None:
        self._outcomes.append(faulted)

    @property
    def observations(self) -> int:
        return len(self._outcomes)

    @property
    def faults(self) -> int:
        return sum(1 for f in self._outcomes if f)

    @property
    def fault_rate(self) -> float:
        """Observed fault rate, or 0.0 with no observations.

        A mechanism nobody has called yet is treated as healthy rather than
        unknown. Treating it as unhealthy would mean a cold start refuses every
        request, which trades one outage for another.
        """
        if not self._outcomes:
            return 0.0
        return self.faults / len(self._outcomes)

    def reset(self) -> None:
        self._outcomes.clear()


@dataclass
class HealthEvent:
    """A recorded change in which mechanism is serving verification."""

    mechanism: str
    event: str
    fault_rate: float
    observations: int
    detail: str


class ResilientVerifier:
    """Routes verification to a healthy mechanism, or refuses.

    Composition, not inheritance: it holds a primary and an optional
    conservative mechanism and implements the same ``Verifier`` Protocol, so
    every caller is unaware it exists. That is the swappability property doing
    real work — resilience was added without touching a single call site.

    Escalation is *sticky within a window*: once the primary trips, traffic
    stays on the conservative mechanism until the primary's window is reset. A
    breaker that flaps between mechanisms on alternating requests produces
    telemetry nobody can interpret.
    """

    def __init__(
        self,
        primary: Any,
        contract: TrustContract,
        *,
        conservative: Any | None = None,
        window_capacity: int = 50,
    ) -> None:
        self._primary = primary
        self._conservative = conservative
        self._threshold, self._min_observations = _resilience_thresholds(contract)
        self._health: dict[str, HealthWindow] = {
            primary.name: HealthWindow(capacity=window_capacity)
        }
        if conservative is not None:
            self._health[conservative.name] = HealthWindow(capacity=window_capacity)
        self._events: list[HealthEvent] = []

    # -- introspection -----------------------------------------------------

    @property
    def name(self) -> str:
        return f"resilient({self._primary.name})"

    @property
    def events(self) -> tuple[HealthEvent, ...]:
        """Health events recorded so far, oldest first."""
        return tuple(self._events)

    def health(self, mechanism: str) -> HealthWindow:
        return self._health.setdefault(mechanism, HealthWindow())

    def is_tripped(self, mechanism: str) -> bool:
        """True when ``mechanism``'s observed fault rate has crossed the bar.

        Requires a minimum number of observations first: a single fault on the
        first call is not a fault *rate*, and tripping on it would make the
        breaker a hair trigger.
        """
        window = self.health(mechanism)
        if window.observations < self._min_observations:
            return False
        return window.fault_rate > self._threshold

    # -- the Verifier protocol --------------------------------------------

    def verify(self, answer: str, evidence: EvidenceSet, question: str) -> VerifierResponse:
        """Verify via the healthiest permitted mechanism, or raise.

        Raises:
            VerifierUnavailable: when no permitted mechanism is healthy. The
                caller refuses. Skipping verification is not among the options.
            VerifierFailure: propagated from the serving mechanism, so the
                decision function converts it into a fail-closed refusal.
        """
        for mechanism in self._candidates():
            if self.is_tripped(mechanism.name):
                continue
            if not _reports_healthy(mechanism):
                self._record(mechanism.name, faulted=True, event="reported_unhealthy")
                continue
            try:
                response: VerifierResponse = mechanism.verify(answer, evidence, question)
            except VerifierFailure:
                self._record(mechanism.name, faulted=True, event="fault")
                if self.is_tripped(mechanism.name) and mechanism is self._primary:
                    self._escalate()
                raise
            self._record(mechanism.name, faulted=False, event="ok")
            return response

        raise VerifierUnavailable(
            "no permitted verification mechanism is healthy; refusing rather than "
            "answering unverified"
        )

    # -- internals ---------------------------------------------------------

    def _candidates(self) -> tuple[Any, ...]:
        if self._conservative is None:
            return (self._primary,)
        return (self._primary, self._conservative)

    def _record(self, mechanism: str, *, faulted: bool, event: str) -> None:
        window = self.health(mechanism)
        window.record(faulted=faulted)
        if faulted:
            self._events.append(
                HealthEvent(
                    mechanism=mechanism,
                    event=event,
                    fault_rate=window.fault_rate,
                    observations=window.observations,
                    detail=f"{mechanism} recorded a fault ({event})",
                )
            )

    def _escalate(self) -> None:
        target = self._conservative.name if self._conservative else "<none configured>"
        self._events.append(
            HealthEvent(
                mechanism=self._primary.name,
                event="escalated",
                fault_rate=self.health(self._primary.name).fault_rate,
                observations=self.health(self._primary.name).observations,
                detail=(
                    f"fault rate exceeded {self._threshold:.0%}; escalating to "
                    f"{target}. Verification is not skipped."
                ),
            )
        )


def _resilience_thresholds(contract: TrustContract) -> tuple[float, int]:
    """Read the breaker's thresholds from the contract, never from constants."""
    for rule in contract.resilience:
        if rule.rule == "degrade_to_conservative_verifier":
            threshold = getattr(rule, "fault_rate_threshold", None)
            minimum = getattr(rule, "minimum_observations", None)
            if isinstance(threshold, int | float) and isinstance(minimum, int):
                return float(threshold), int(minimum)
    raise ValueError("contract declares no resilience thresholds (ET-RES-001)")


def _reports_healthy(mechanism: Any) -> bool:
    """Treat a mechanism without a health property as healthy.

    Health reporting is an optional capability. Requiring it would make every
    simple verifier implement a property it has no way to answer meaningfully.
    """
    healthy = getattr(mechanism, "healthy", True)
    return bool(healthy)
