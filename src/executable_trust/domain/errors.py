"""Exception hierarchy.

Two families, and the distinction matters:

**Configuration and integrity failures** (:class:`ContractError` and
subclasses, :class:`TraceabilityError`) are raised. They mean the system is not
in a state where it can make a governed decision at all — a malformed contract,
an unratified one, a reason code that is not in the controlled set. Raising is
correct: there is no safe answer to return.

**Runtime refusals are not exceptions.** A request that fails authorization,
evidence sufficiency, or claim verification returns a ``REFUSED``
:class:`~executable_trust.verification.models.VerificationDecision` with a
controlled reason code. A refusal is a *successful governed outcome*, not an
error, and modelling it as an exception would tempt callers to catch and
continue.

The one bridge between the families is :class:`VerifierFailure`, which a
verification mechanism raises and the decision function catches and converts
into a fail-closed refusal.
"""

from __future__ import annotations


class ExecutableTrustError(Exception):
    """Base class for every error raised by this package."""


# ---------------------------------------------------------------------------
# Contract errors — the system cannot govern a decision at all
# ---------------------------------------------------------------------------


class ContractError(ExecutableTrustError):
    """Base for failures to load, validate, or resolve a trust contract."""


class ContractNotFound(ContractError):
    """No contract is registered under the requested identifier and version."""


class ContractNotRatified(ContractError):
    """The resolved contract exists but is not in ``ratified`` status.

    A draft, superseded, or expired contract describes an intention or a
    history. Neither may govern a live decision.
    """


class ContractValidationError(ContractError):
    """A contract does not satisfy ``schemas/trust-contract.schema.json``.

    Also raised when the contract is structurally valid but disagrees with the
    implementation's vocabulary — for example, declaring a response strategy
    the code does not implement. Disagreement between contract and code is a
    defect in one of them, never a preference to be resolved silently.
    """


class UncontrolledReasonCode(ContractError):
    """A reason code was used that the governing contract does not declare.

    The correct response is a contract amendment, never a new code invented at
    the call site.
    """


# ---------------------------------------------------------------------------
# Lifecycle errors — an invalid transition is refused before anything is stored
# ---------------------------------------------------------------------------


class LifecycleError(ExecutableTrustError):
    """Base for lifecycle transition failures."""


class InvalidTransition(LifecycleError):
    """The requested state transition is not declared by the contract.

    Raised at the domain boundary *and* re-checked at the persistence boundary,
    because a transition merely absent from an interface is bypassed by anyone
    calling the API directly.
    """


class MissingAccountableReview(LifecycleError):
    """A transition requiring accountable human review lacked attribution.

    Either no actor was supplied, the actor was a system rather than a
    principal, or no role was recorded. All three mean nobody is accountable
    for the decision.
    """


class ImmutableRecordViolation(LifecycleError):
    """An attempt was made to mutate a stored decision record.

    Corrections create a superseding record. Nothing is ever edited in place.
    """


# ---------------------------------------------------------------------------
# Verification errors
# ---------------------------------------------------------------------------


class VerifierFailure(ExecutableTrustError):
    """A verification mechanism could not produce a usable result.

    Raised by verifier implementations and caught by the decision function,
    which converts it into a fail-closed refusal carrying the mapped reason
    code. Carrying the code on the exception keeps the mapping with the
    mechanism that knows what went wrong, rather than inferring it from an
    exception type at the catch site.
    """

    def __init__(self, message: str, *, reason_code: str) -> None:
        super().__init__(message)
        self.reason_code = reason_code


class VerifierTimeout(VerifierFailure):
    """The verification call exceeded its declared budget."""

    def __init__(self, message: str = "verification call exceeded its budget") -> None:
        super().__init__(message, reason_code="verifier_timeout")


class VerifierUnavailable(VerifierFailure):
    """No permitted verification mechanism is healthy.

    Never a licence to skip verification: the caller refuses instead.
    """

    def __init__(self, message: str = "no permitted verification mechanism is available") -> None:
        super().__init__(message, reason_code="no_verifier_available")


# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------


class TraceabilityError(ExecutableTrustError):
    """A contract rule identifier has no corresponding test, or vice versa.

    This turns "every rule is tested" from a claim in a document into a build
    failure.
    """
