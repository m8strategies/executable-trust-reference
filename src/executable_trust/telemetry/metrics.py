"""Honest metrics over runtime telemetry (ET-TEL-004/005/006).

Three rules, and each one exists because the alternative is a number that
reassures rather than informs.

**Counts are never withheld.** A consumer can always see how many decisions the
window holds.

**Rates are withheld below the contract's minimum sample.** A grounded-rate of
100% computed from three decisions is worse than no number. The rate key stays
present and null so the payload shape never changes, and the sample size and
threshold ship alongside so a consumer can render "6 of 10 needed" instead of a
blank.

**Runtime telemetry makes no quality claim.** These metrics describe *behaviour*
— what the system decided. *Quality* — how often it was right — is claimed only
by the offline baseline, which has human-authored ground truth. The
``quality_note`` travels inside the payload rather than sitting in
documentation, so a consumer cannot render the numbers without the caveat being
available.

Blending "how often we answered" with "how often we were correct", using
whichever is more impressive where it is needed, is where Executable Trust
reverts to governance as marketing.
"""

from __future__ import annotations

from collections import Counter

from pydantic import BaseModel, ConfigDict, Field

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import DecisionOutcome, Environment, Population
from executable_trust.telemetry.events import TelemetryEvent

#: Shipped in every metrics payload. The boundary is stated in the interface
#: itself, not only in a document nobody reads at the moment of use.
QUALITY_NOTE = (
    "Runtime telemetry describes behavior — what the system decided. "
    "Quality — how often decisions are correct — is claimed only by the offline "
    "evaluation baseline, which has human-authored ground truth. This payload "
    "never reports accuracy."
)


class PopulationSummary(BaseModel):
    """Which events the metrics were computed over, and which were excluded."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    environments_included: tuple[str, ...]
    observed_events: int = Field(ge=0)
    synthetic_events_excluded: int = Field(ge=0)
    other_environment_events_excluded: int = Field(ge=0)


class BehaviorMetrics(BaseModel):
    """Behavioural metrics over a telemetry window.

    Every rate field is ``float | None``. ``None`` means withheld for
    insufficient sample, never zero — a withheld rate and a rate of zero are
    completely different facts and sharing a representation would merge them.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    total: int = Field(ge=0)
    minimum_sample: int = Field(ge=1)
    insufficient_sample: bool

    counts: dict[str, int]
    reason_code_counts: dict[str, int]

    grounded_rate: float | None = None
    refused_rate: float | None = None
    fault_rate: float | None = None

    latency_ms_p50: int | None = None
    latency_ms_p95: int | None = None
    latency_observations: int = Field(ge=0)

    population: PopulationSummary
    quality_note: str = QUALITY_NOTE


def observed_events(
    events: tuple[TelemetryEvent, ...],
    contract: TrustContract,
) -> tuple[TelemetryEvent, ...]:
    """Filter a window down to events that may be described as observed.

    Applies the contract's ``observed_metric_environments`` and keeps only the
    observed population. This is the mechanism that stops a test run's fixture
    decisions being aggregated into a number claimed to describe production —
    the exact contamination the paper's Layer 5 narrative describes.
    """
    permitted = {
        Environment(e) for e in contract.telemetry.populations.observed_metric_environments
    }
    return tuple(
        e for e in events if e.environment in permitted and e.population is Population.OBSERVED
    )


def compute_behavior_metrics(
    events: tuple[TelemetryEvent, ...],
    contract: TrustContract,
    *,
    observed_only: bool = True,
) -> BehaviorMetrics:
    """Compute behavioural metrics, withholding rates below the minimum sample.

    Args:
        events: the raw telemetry window.
        contract: supplies the minimum sample and the permitted environments.
        observed_only: when true (the default), synthetic and non-permitted
            environments are excluded before anything is computed. Passing
            false is legitimate for a diagnostic view, but such a view must not
            be labelled observed.
    """
    permitted = {
        Environment(e) for e in contract.telemetry.populations.observed_metric_environments
    }

    window = observed_events(events, contract) if observed_only else events

    synthetic_excluded = sum(1 for e in events if e.population is not Population.OBSERVED)
    other_env_excluded = sum(
        1 for e in events if e.population is Population.OBSERVED and e.environment not in permitted
    )

    minimum = contract.minimum_sample()
    total = len(window)
    sufficient = total >= minimum

    grounded = sum(1 for e in window if e.outcome is DecisionOutcome.GROUNDED)
    refused = total - grounded
    faults = sum(1 for e in window if e.is_fault)

    reason_counts = Counter(e.reason_code.value for e in window if e.reason_code is not None)

    latencies = sorted(e.latency_ms for e in window)

    return BehaviorMetrics(
        total=total,
        minimum_sample=minimum,
        insufficient_sample=not sufficient,
        counts={"grounded": grounded, "refused": refused, "faults": faults},
        reason_code_counts=dict(sorted(reason_counts.items())),
        grounded_rate=_rate(grounded, total, sufficient),
        refused_rate=_rate(refused, total, sufficient),
        fault_rate=_rate(faults, total, sufficient),
        # Latency is a measurement, not a rate: a median of four observations is
        # a real median of four observations. It is not gated, but the number of
        # observations ships beside it so the reader can judge its weight.
        latency_ms_p50=_percentile(latencies, 0.50),
        latency_ms_p95=_percentile(latencies, 0.95),
        latency_observations=len(latencies),
        population=PopulationSummary(
            environments_included=tuple(sorted(e.value for e in permitted))
            if observed_only
            else ("<all>",),
            observed_events=total,
            synthetic_events_excluded=synthetic_excluded if observed_only else 0,
            other_environment_events_excluded=other_env_excluded if observed_only else 0,
        ),
    )


def _rate(numerator: int, denominator: int, sufficient: bool) -> float | None:
    """Return a rate, or ``None`` when the sample is too small to report one."""
    if not sufficient or denominator == 0:
        return None
    return round(numerator / denominator, 4)


def _percentile(sorted_values: list[int], fraction: float) -> int | None:
    """Nearest-rank percentile over a pre-sorted list, or ``None`` if empty."""
    if not sorted_values:
        return None
    index = max(0, min(len(sorted_values) - 1, round(fraction * len(sorted_values)) - 1))
    return sorted_values[index]
