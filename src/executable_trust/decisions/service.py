"""The governed request path.

One request, in order, with every exit fail-closed:

1. **Resolve the contract.** Unknown or unratified fails closed before anything
   else happens. A system that cannot say which rules apply cannot apply them.
2. **Authorize.** Before retrieval. A denied request exits having read no
   evidence.
3. **Check evidence provenance and sufficiency.** Before generation. The
   generator is never invoked for a request that will refuse.
4. **Generate**, only now.
5. **Verify**, and map the verifier's output through the decision function.
6. **Record** an immutable decision, then capture telemetry — fail-open, after
   the decision is already final.

Refusals are short-circuits, not error handlers. Each of the three refusal
points above exits before the work it guards, which is cheaper, safer, and more
honest than generating an answer and discarding it.

The generator is a plain callable. This repository is not about generation: it
is about what surrounds it. Substituting a real model changes nothing here.
"""

from __future__ import annotations

from executable_trust.authorization.protocol import AuthorizationDecision, Authorizer
from executable_trust.contracts.registry import ContractRegistry
from executable_trust.decisions.models import Generator, GovernedResult
from executable_trust.decisions.records import DecisionRecord
from executable_trust.decisions.store import InMemoryDecisionStore
from executable_trust.domain.enums import (
    AuthorizationResult,
    DecisionOutcome,
    Environment,
    EvidenceQuality,
    Population,
    ReasonCode,
)
from executable_trust.domain.errors import (
    ContractNotFound,
    ContractNotRatified,
    VerifierFailure,
)
from executable_trust.domain.identifiers import Clock, IdFactory
from executable_trust.domain.models import ClaimCounts, TrustRequest
from executable_trust.evidence.gate import check_provenance, evaluate_gate
from executable_trust.evidence.models import EvidenceSet
from executable_trust.telemetry.recorder import TelemetryRecorder
from executable_trust.verification.decision_function import decide
from executable_trust.verification.models import VerificationDecision
from executable_trust.verification.protocol import Verifier


class TrustService:
    """Composition root for the governed request path."""

    def __init__(
        self,
        registry: ContractRegistry,
        *,
        authorizer: Authorizer,
        verifier: Verifier,
        generator: Generator,
        store: InMemoryDecisionStore,
        recorder: TelemetryRecorder,
        clock: Clock,
        ids: IdFactory,
        environment: Environment = Environment.PRODUCTION,
        population: Population = Population.OBSERVED,
    ) -> None:
        self._registry = registry
        self._authorizer = authorizer
        self._verifier = verifier
        self._generator = generator
        self._store = store
        self._recorder = recorder
        self._clock = clock
        self._ids = ids
        self._environment = environment
        self._population = population

    def handle(self, request: TrustRequest, evidence: EvidenceSet) -> GovernedResult:
        """Run one request through the full governed path."""

        # --- 1. Contract resolution --------------------------------------
        # Fails closed before any other work. Note the reason codes differ:
        # "we do not carry that version" and "that version exists but is not
        # ratified" are different failures and an operator needs to tell them
        # apart.
        try:
            contract = self._registry.resolve(request.contract_id, request.contract_version)
        except ContractNotFound as exc:
            return self._refuse_without_contract(
                request, evidence, ReasonCode.CONTRACT_VERSION_UNKNOWN, str(exc)
            )
        except ContractNotRatified as exc:
            return self._refuse_without_contract(
                request, evidence, ReasonCode.CONTRACT_NOT_RATIFIED, str(exc)
            )

        # --- 2. Authorization, before retrieval --------------------------
        authorization = self._authorizer.authorize(request.actor, request.resource)
        if not authorization.allowed:
            decision = VerificationDecision.refuse(
                ReasonCode.AUTHORIZATION_DENIED,
                mechanism="authorization",
                detail=authorization.reason,
            )
            return self._finalize(
                request,
                # Zero evidence: authorization precedes retrieval, so a denied
                # request genuinely read nothing.
                EvidenceSet(evidence_set_ref=evidence.evidence_set_ref),
                contract_id=contract.contract_id,
                contract_version=contract.version,
                decision=decision,
                authorization=authorization,
                evidence_quality=None,
                generation_invoked=False,
            )

        # --- 3a. Evidence provenance -------------------------------------
        provenance_failure = check_provenance(evidence, contract)
        if provenance_failure is not None:
            decision = VerificationDecision.refuse(
                ReasonCode.EVIDENCE_PROVENANCE_INVALID,
                mechanism="evidence-gate",
                detail=provenance_failure,
            )
            return self._finalize(
                request,
                evidence,
                contract_id=contract.contract_id,
                contract_version=contract.version,
                decision=decision,
                authorization=authorization,
                evidence_quality=None,
                generation_invoked=False,
            )

        # --- 3b. Evidence sufficiency ------------------------------------
        gate = evaluate_gate(evidence, contract)
        if not gate.sufficient:
            decision = VerificationDecision.refuse(
                ReasonCode.INSUFFICIENT_EVIDENCE,
                mechanism="evidence-gate",
                detail=gate.detail,
            )
            return self._finalize(
                request,
                evidence,
                contract_id=contract.contract_id,
                contract_version=contract.version,
                decision=decision,
                authorization=authorization,
                evidence_quality=gate.quality,
                generation_invoked=False,
            )

        # --- 4. Generation, only now -------------------------------------
        window = evidence.truncated_to(contract.evidence.gate.top_k)
        answer = self._generator(request.question, window)

        # --- 5. Verification ---------------------------------------------
        try:
            response = self._verifier.verify(answer, window, request.question)
        except VerifierFailure as exc:
            # The verifier carries the reason code describing its own fault, so
            # the catch site does not have to infer it from an exception type.
            decision = VerificationDecision.refuse(
                _reason_code_or_error(exc.reason_code),
                mechanism=getattr(self._verifier, "name", "unknown"),
                detail=str(exc),
            )
        else:
            decision = decide(response, contract)

        return self._finalize(
            request,
            window,
            contract_id=contract.contract_id,
            contract_version=contract.version,
            decision=decision,
            authorization=authorization,
            evidence_quality=gate.quality,
            generation_invoked=True,
        )

    # -- internals ---------------------------------------------------------

    def _refuse_without_contract(
        self,
        request: TrustRequest,
        evidence: EvidenceSet,
        reason_code: ReasonCode,
        detail: str,
    ) -> GovernedResult:
        """Refuse when no contract governs.

        The record still names the version the *request* asked for. Recording a
        blank would lose the only fact that explains the refusal, and the
        record must remain readable by someone investigating why a request was
        turned away.
        """
        decision = VerificationDecision.refuse(
            reason_code, mechanism="contract-resolution", detail=detail
        )
        return self._finalize(
            request,
            EvidenceSet(evidence_set_ref=evidence.evidence_set_ref),
            contract_id=request.contract_id,
            contract_version=request.contract_version,
            decision=decision,
            authorization=AuthorizationDecision.deny("contract unresolved: not evaluated"),
            evidence_quality=None,
            generation_invoked=False,
            authorization_result=AuthorizationResult.DENIED,
        )

    def _finalize(
        self,
        request: TrustRequest,
        evidence: EvidenceSet,
        *,
        contract_id: str,
        contract_version: str,
        decision: VerificationDecision,
        authorization: AuthorizationDecision,
        evidence_quality: EvidenceQuality | None,
        generation_invoked: bool,
        authorization_result: AuthorizationResult | None = None,
    ) -> GovernedResult:
        """Record the decision, then capture telemetry.

        Order matters and is not negotiable: the decision is stored and final
        *before* capture is attempted. Capture cannot influence it, because by
        the time capture runs there is nothing left to influence.
        """
        record = DecisionRecord(
            decision_id=self._ids.new_id("dec"),
            recorded_at=self._clock.now(),
            contract_id=contract_id,
            contract_version=contract_version,
            correlation_id=request.correlation_id,
            subject_id=request.actor.actor_id,
            request_ref=request.resource,
            evidence_set_ref=evidence.evidence_set_ref,
            authorization_result=authorization_result or authorization.result,
            outcome=decision.outcome,
            strategy=decision.strategy,
            reason_code=decision.reason_code,
            verification_mechanism=decision.mechanism,
            evidence_count=evidence.count,
            claim_counts=decision.claim_counts
            if decision.claim_counts.measured
            else ClaimCounts.not_measured(),
            latency_ms=decision.latency_ms,
            population=self._population,
            environment=self._environment,
        )
        self._store.append(record)

        event = self._recorder.record(record, evidence_quality=evidence_quality)

        return GovernedResult(
            decision=decision,
            record=record,
            authorization=authorization,
            evidence_quality=evidence_quality,
            generation_invoked=generation_invoked,
            telemetry_captured=event is not None,
        )


def _reason_code_or_error(raw: str) -> ReasonCode:
    """Map a verifier's declared reason code, defaulting to a generic fault.

    An unrecognised code becomes ``verifier_error`` rather than propagating an
    uncontrolled string. The system still refuses either way; what is protected
    here is the controlled vocabulary.
    """
    try:
        return ReasonCode(raw)
    except ValueError:
        return ReasonCode.VERIFIER_ERROR


def refused_for(result: GovernedResult, reason_code: ReasonCode) -> bool:
    """Readability helper for tests and examples."""
    return (
        result.decision.outcome is DecisionOutcome.REFUSED
        and result.decision.reason_code is reason_code
    )
