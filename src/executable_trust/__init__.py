"""Executable Trust — reference implementation.

An independent reference implementation of the mechanisms described in
*Executable Trust: The Runtime Architecture of Production-Ready Enterprise AI*
by Moataz Mahmoud (M8 Strategies).

Executable Trust is enterprise trust implemented as a runtime capability:
something a platform *does* on every request rather than something an
organization *writes* about its platform. It is defined by four properties:

**Versioned**
    The rules carry a version identifier. Every behavior change traces to a
    specific rule revision. See :mod:`executable_trust.contracts`.

**Enforced**
    The system does not log a violation; it refuses to proceed. See
    :mod:`executable_trust.verification` and :mod:`executable_trust.evidence`.

**Independently Measured**
    Something outside the enforcement path checks whether the enforcement path
    does what it claims. See :mod:`executable_trust.evaluation`.

**Ratified**
    A rule change is a deliberate, documented, dated act. See
    :mod:`executable_trust.amendments`.

Scope
-----
This repository provides an independent reference implementation of the
mechanisms described in the paper. Its design is informed by lessons from a
working production enterprise AI platform, while the implementation, examples,
contracts, and evaluation data included here are publication-safe and
independently reproducible. The repository excludes the commercial platform,
proprietary integrations, production prompts, operational data, customer
information, and internal deployment architecture.

The package runs with no model provider, no cloud credentials, no database, and
no network access. Every verifier is deterministic and every fixture is
synthetic.
"""

from executable_trust.domain.enums import (
    ClaimVerdict,
    DecisionOutcome,
    LifecycleState,
    ReasonCode,
    ResponseStrategy,
)

__version__ = "0.1.0"

__all__ = [
    "ClaimVerdict",
    "DecisionOutcome",
    "LifecycleState",
    "ReasonCode",
    "ResponseStrategy",
    "__version__",
]
