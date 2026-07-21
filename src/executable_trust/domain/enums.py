"""Controlled vocabulary for the Executable Trust reference implementation.

Three categories live here, and they are deliberately kept apart:

``ClaimVerdict``
    Claim-level classification. The word *verdict* is reserved for this and
    nothing else.

``DecisionOutcome`` / ``ResponseStrategy``
    Decision-level. ``REFUSED`` is an outcome and is deliberately **not** also
    a strategy: modelling it in both places would duplicate one fact across two
    semantic axes, and the pair would eventually disagree. A refused decision
    carries no strategy at all — absence is the correct representation.

``ReasonCode``
    Decision-level explanation. Distinct from ``ClaimVerdict`` because "why the
    system refused" and "how one claim compared to the evidence" are different
    questions with different audiences.

The enum members below are the *implementation's* vocabulary. The authoritative
vocabulary is the versioned contract; :mod:`executable_trust.contracts.validation`
checks that the two agree, and a mismatch fails closed rather than silently
preferring the code.
"""

from __future__ import annotations

from enum import StrEnum


class ClaimVerdict(StrEnum):
    """How one decomposed claim compares to the evidence retrieved for a request.

    There is no fourth member. A confidently phrased claim that no evidence
    entails is ``UNSUPPORTED``; there is no category where good prose earns a
    pass.
    """

    SUPPORTED = "SUPPORTED"
    """Entailed by an evidence item retrieved for this request."""

    UNSUPPORTED = "UNSUPPORTED"
    """Not entailed by any retrieved evidence item. Absent, not disproven."""

    CONTRADICTED = "CONTRADICTED"
    """A retrieved evidence item asserts the opposite."""


class DecisionOutcome(StrEnum):
    """The two external states a governed decision may end in."""

    GROUNDED = "GROUNDED"
    """Every presented statement is supported by evidence."""

    REFUSED = "REFUSED"
    """The system declines to answer from governed evidence."""


class ResponseStrategy(StrEnum):
    """How a *grounded* answer is presented.

    Only meaningful when the outcome is ``GROUNDED``. A refused decision has no
    strategy; see the module docstring.
    """

    DIRECT = "DIRECT"
    """Grounded, with nothing to bound."""

    BOUNDED = "BOUNDED"
    """Grounded, and explicitly stating what the evidence does not cover."""


class ReasonCode(StrEnum):
    """Controlled decision-level explanations.

    Every member must be declared in ``contracts/reason-codes-v1.0.yaml`` and
    must map to at least one test. ``scripts/validate_traceability.py`` fails
    the build if either link is missing, so this enum cannot drift away from
    the contract that governs it.

    Members are grouped by origin: codes the paper names explicitly, and codes
    derived for fail-closed paths the paper describes without naming.
    """

    # -- Named by the paper ------------------------------------------------
    UNSUPPORTED_CLAIM = "unsupported_claim"
    NO_SUPPORTED_CLAIMS = "no_supported_claims"
    DOES_NOT_ADDRESS_QUESTION = "does_not_address_question"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

    # -- Derived: fail-closed paths the paper describes but does not name ---
    EMPTY_CLAIM_SET = "empty_claim_set"
    MISSING_CLAIM_VERDICT = "missing_claim_verdict"
    UNKNOWN_CLAIM_VERDICT = "unknown_claim_verdict"
    MALFORMED_VERIFIER_OUTPUT = "malformed_verifier_output"
    VERIFIER_ERROR = "verifier_error"
    VERIFIER_TIMEOUT = "verifier_timeout"
    VERIFIER_OUTPUT_TRUNCATED = "verifier_output_truncated"
    NO_VERIFIER_AVAILABLE = "no_verifier_available"
    AUTHORIZATION_DENIED = "authorization_denied"
    EVIDENCE_PROVENANCE_INVALID = "evidence_provenance_invalid"
    CONTRACT_VERSION_UNKNOWN = "contract_version_unknown"
    CONTRACT_NOT_RATIFIED = "contract_not_ratified"
    CONTRACT_UNRESOLVED = "contract_unresolved"

    # -- Lifecycle ---------------------------------------------------------
    REVIEW_ACCEPTED = "review.accepted"
    REVIEW_REJECTED = "review.rejected"
    SUPERSESSION_REPLACED = "supersession.replaced"


class AuthorizationResult(StrEnum):
    """Outcome of the authorization check that precedes retrieval."""

    ALLOWED = "ALLOWED"
    DENIED = "DENIED"


class EvidenceQuality(StrEnum):
    """Coarse label for a retrieved evidence set.

    ``EMPTY`` is kept distinct from ``INSUFFICIENT`` because "we found nothing"
    and "we found something too weak to use" are different operational
    problems, even though both refuse under the same reason code.
    """

    SUFFICIENT = "sufficient"
    INSUFFICIENT = "insufficient"
    EMPTY = "empty"


class LifecycleState(StrEnum):
    """States of a decision record, on the paper's decision-record axis.

    This is not a request or workflow lifecycle. It describes one artifact:
    proposed by the system, reviewed by an accountable human, and eventually
    replaced.
    """

    PROPOSED = "PROPOSED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class ActorType(StrEnum):
    """Who performed an act.

    A transition requiring accountable human review must be attributed to a
    ``PRINCIPAL``. A ``SYSTEM`` actor can never satisfy that requirement, which
    is what makes "reviewed by a human" checkable rather than aspirational.
    """

    PRINCIPAL = "principal"
    SYSTEM = "system"


class Environment(StrEnum):
    """Deployment that produced an event.

    Resolution is conservative: an unrecognized environment is treated as the
    most restrictive one rather than assumed to be a development box.
    """

    PRODUCTION = "production"
    STAGING = "staging"
    DEVELOPMENT = "development"
    TEST = "test"


class Population(StrEnum):
    """Whether an event describes real or generated activity.

    Classification is conservative by construction: anything not explicitly
    marked observed is synthetic. The failure this prevents is a fixture
    quietly counted as production behavior.
    """

    OBSERVED = "observed"
    SYNTHETIC = "synthetic"


class RatificationStatus(StrEnum):
    """Whether a contract may govern a decision.

    Only ``RATIFIED`` may. Every other status fails closed — a draft contract
    describes an intention, not a rule.
    """

    DRAFT = "draft"
    RATIFIED = "ratified"
    SUPERSEDED = "superseded"
    EXPIRED = "expired"


#: Reason codes that explain a lifecycle transition rather than a verification
#: decision. Kept as a set so :mod:`executable_trust.contracts.validation` can
#: check that every *other* code declares the outcome it applies to.
LIFECYCLE_REASON_CODES: frozenset[ReasonCode] = frozenset(
    {
        ReasonCode.REVIEW_ACCEPTED,
        ReasonCode.REVIEW_REJECTED,
        ReasonCode.SUPERSESSION_REPLACED,
    }
)
