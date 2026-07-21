"""The decision function: pure, deterministic, fail-closed.

This is the paper's ``decide()`` made complete. The policy sentence and the
function are the same rule in two languages, which is the entire discipline —
not clever code, but zero daylight between what the contract says and what the
function does.

The guard order below is part of the contract (``verification.rules``), not an
implementation detail. Reordering changes which reason code a request receives,
and reason codes are the audit surface.

Nothing in this module performs I/O, reads a clock, or calls a model. Given the
same inputs it returns the same decision forever, which is what makes it
testable as a pure function and reproducible as a baseline.
"""

from __future__ import annotations

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import ClaimVerdict, ReasonCode, ResponseStrategy
from executable_trust.domain.errors import VerifierFailure
from executable_trust.domain.models import Claim, ClaimCounts
from executable_trust.verification.models import (
    VerificationDecision,
    VerifierResponse,
    parse_claims,
)


def decide(
    response: VerifierResponse,
    contract: TrustContract,
) -> VerificationDecision:
    """Map a verifier response to a governed decision.

    Guards run in contract order:

    1. truncated output (ET-VER-011)
    2. malformed / missing / unknown verdicts, via parsing (ET-VER-008/002/003)
    3. empty claim set (ET-VER-001)
    4. no SUPPORTED claim at all (ET-VER-005)
    5. some claims UNSUPPORTED or CONTRADICTED (ET-VER-004)
    6. missing or false ``answers_question`` (ET-VER-008 / ET-VER-006)
    7. strategy selection (ET-VER-007)

    Every exit before step 7 is a refusal carrying a controlled reason code.
    Step 7 is the only path that produces a grounded answer.
    """
    mechanism = response.mechanism
    latency = response.latency_ms

    # --- 1. Truncation is checked before parsing -------------------------
    # A response cut off at a size cap may parse into a *prefix* of the claims
    # the verifier intended to emit. Parsing it first would silently drop the
    # unexamined tail — which is exactly the set most likely to contain the
    # unsupported claim. Its own reason code separates capacity from faults.
    if response.truncated:
        return VerificationDecision.refuse(
            ReasonCode.VERIFIER_OUTPUT_TRUNCATED,
            mechanism=mechanism,
            latency_ms=latency,
            detail="verifier output was truncated; the claim set may be incomplete",
        )

    # --- 2. Parse, failing closed on malformed/missing/unknown verdicts ---
    try:
        claims = parse_claims(response.claims)
    except VerifierFailure as exc:
        return VerificationDecision.refuse(
            ReasonCode(exc.reason_code),
            mechanism=mechanism,
            latency_ms=latency,
            detail=str(exc),
        )

    counts = ClaimCounts.from_claims(claims)

    # --- 3. An empty claim set has verified nothing ----------------------
    # A verifier that decomposes an answer into zero claims has not found the
    # answer acceptable; it has failed to examine it. Distinguished from
    # "every claim was rejected" so telemetry separates a degenerate verifier
    # from a genuinely unsupportable answer.
    if not claims:
        return VerificationDecision.refuse(
            ReasonCode.EMPTY_CLAIM_SET,
            mechanism=mechanism,
            latency_ms=latency,
            claim_counts=counts,
            detail="verifier returned zero claims; nothing was verified",
        )

    # --- 4. Not one claim survived contact with the evidence --------------
    # Checked before the mixed case so that "nothing was supportable" and "some
    # of this was supportable" carry different reason codes. Both refuse; the
    # distinction is for the operator reading telemetry, where a run of
    # wholly-unsupportable answers points at retrieval and a run of partially
    # supported ones points at generation.
    #
    # This order is the paper's order and the contract's order. It changes no
    # outcome — every path here refuses — only which controlled code is
    # recorded. See docs/paper-to-code-traceability.md (ET-VER-004/005).
    supported = [c for c in claims if c.verdict is ClaimVerdict.SUPPORTED]
    if not supported:
        return VerificationDecision.refuse(
            ReasonCode.NO_SUPPORTED_CLAIMS,
            mechanism=mechanism,
            latency_ms=latency,
            claims=claims,
            claim_counts=counts,
            detail=(
                f"none of {len(claims)} claim(s) were supported by the evidence "
                "retrieved for this request"
            ),
        )

    # --- 5. Any unverified factual assertion refuses the whole answer -----
    # Not repaired in place: a repair produced by the same mechanism that
    # produced the flawed answer is itself an unverified generation. See
    # contracts/amendments/example-amendment-v1.0-a1.yaml.
    rejected = [c for c in claims if c.verdict is not ClaimVerdict.SUPPORTED]
    if rejected:
        return VerificationDecision.refuse(
            ReasonCode.UNSUPPORTED_CLAIM,
            mechanism=mechanism,
            latency_ms=latency,
            claims=claims,
            claim_counts=counts,
            detail=(
                f"{len(rejected)} of {len(claims)} claim(s) were not supported by the "
                f"evidence retrieved for this request"
            ),
        )

    # --- 6. Relevance ----------------------------------------------------
    # A missing value is malformed output, never an implied yes. This is the
    # single most important line in the module: defaulting it to True would
    # mean a verifier that stopped emitting the field silently promoted every
    # answer it saw.
    if response.answers_question is None:
        return VerificationDecision.refuse(
            ReasonCode.MALFORMED_VERIFIER_OUTPUT,
            mechanism=mechanism,
            latency_ms=latency,
            claims=claims,
            claim_counts=counts,
            detail=(
                "verifier omitted the required answers_question field; "
                "a missing required field is malformed output, not an implied yes"
            ),
        )

    # A truthful statement that does not address the question is not an answer.
    if not response.answers_question:
        return VerificationDecision.refuse(
            ReasonCode.DOES_NOT_ADDRESS_QUESTION,
            mechanism=mechanism,
            latency_ms=latency,
            claims=claims,
            claim_counts=counts,
            detail="supported claims do not address the question that was asked",
        )

    # --- 7. Strategy selection: the only grounded exit --------------------
    strategy = _select_strategy(claims)
    return VerificationDecision.ground(
        strategy,
        mechanism=mechanism,
        claims=claims,
        latency_ms=latency,
        detail=_strategy_detail(strategy, contract),
    )


def _select_strategy(claims: tuple[Claim, ...]) -> ResponseStrategy:
    """BOUNDED when any claim states a scope limitation, otherwise DIRECT.

    The default is DIRECT rather than BOUNDED because claiming a limitation the
    answer does not actually state would be its own small dishonesty.
    """
    if any(c.states_scope_limitation for c in claims):
        return ResponseStrategy.BOUNDED
    return ResponseStrategy.DIRECT


def _strategy_detail(strategy: ResponseStrategy, contract: TrustContract) -> str:
    version = contract.version
    if strategy is ResponseStrategy.BOUNDED:
        return f"grounded under contract v{version}; answer states a scope limitation"
    return f"grounded under contract v{version}; no scope limitation stated"
