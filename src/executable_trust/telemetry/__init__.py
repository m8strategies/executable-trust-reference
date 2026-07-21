"""Fail-open telemetry capture and honest metrics."""

from executable_trust.telemetry.events import (
    TelemetryEvent,
    classify_environment,
    classify_population,
)
from executable_trust.telemetry.metrics import (
    QUALITY_NOTE,
    BehaviorMetrics,
    PopulationSummary,
    compute_behavior_metrics,
    observed_events,
)
from executable_trust.telemetry.recorder import TelemetryRecorder
from executable_trust.telemetry.store import (
    AlwaysFailingTelemetryStore,
    InMemoryTelemetryStore,
    TelemetryStore,
)

__all__ = [
    "QUALITY_NOTE",
    "AlwaysFailingTelemetryStore",
    "BehaviorMetrics",
    "InMemoryTelemetryStore",
    "PopulationSummary",
    "TelemetryEvent",
    "TelemetryRecorder",
    "TelemetryStore",
    "classify_environment",
    "classify_population",
    "compute_behavior_metrics",
    "observed_events",
]
