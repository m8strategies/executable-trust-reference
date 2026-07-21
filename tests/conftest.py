"""Shared fixtures.

Everything here is deterministic and offline. No fixture reaches a network, a
database, a model provider, or a credential store — which is what lets the test
suite double as the proof of the repository's "runs with no external services"
claim.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from executable_trust.authorization import DeterministicAuthorizer
from executable_trust.contracts import build_default_registry
from executable_trust.contracts.models import TrustContract
from executable_trust.contracts.registry import ContractRegistry
from executable_trust.decisions import InMemoryDecisionStore, TrustService
from executable_trust.domain.enums import ActorType, Environment, Population
from executable_trust.domain.identifiers import FixedClock, SequentialIdFactory
from executable_trust.domain.models import Actor, TrustRequest
from executable_trust.evidence import EvidenceItem, EvidenceSet
from executable_trust.lifecycle import InMemoryTransitionLog, LifecycleStateMachine
from executable_trust.telemetry import InMemoryTelemetryStore, TelemetryRecorder
from executable_trust.verification import ScriptedVerifier

REPO_ROOT = Path(__file__).resolve().parents[1]
CONTRACT_ID = "executable-trust-reference"


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture
def registry() -> ContractRegistry:
    return build_default_registry()


@pytest.fixture
def contract(registry: ContractRegistry) -> TrustContract:
    return registry.resolve(CONTRACT_ID, "1.0")


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock()


@pytest.fixture
def ids() -> SequentialIdFactory:
    return SequentialIdFactory(seed="test")


@pytest.fixture
def engineer() -> Actor:
    return Actor(actor_id="avery-stone", actor_type=ActorType.PRINCIPAL, role="engineer")


@pytest.fixture
def architect() -> Actor:
    return Actor(actor_id="jordan-reyes", actor_type=ActorType.PRINCIPAL, role="architect")


@pytest.fixture
def contractor() -> Actor:
    """A recognised role that holds no resource grants."""
    return Actor(actor_id="casey-lindqvist", actor_type=ActorType.PRINCIPAL, role="contractor")


@pytest.fixture
def system_actor() -> Actor:
    """A system actor. Can never satisfy an accountable-human requirement."""
    return Actor(actor_id="scheduler", actor_type=ActorType.SYSTEM)


@pytest.fixture
def good_evidence() -> EvidenceSet:
    """Evidence that clears the contract gate and carries permitted provenance."""
    return EvidenceSet(
        evidence_set_ref="ev-test-1",
        items=(
            EvidenceItem(
                evidence_id="hb-cr-004",
                text="An approved code review remains valid for 14 calendar days.",
                relevance_score=0.9,
                provenance="governed_corpus",
            ),
        ),
    )


@pytest.fixture
def telemetry_store() -> InMemoryTelemetryStore:
    return InMemoryTelemetryStore()


@pytest.fixture
def decision_store() -> InMemoryDecisionStore:
    return InMemoryDecisionStore()


@pytest.fixture
def recorder(
    telemetry_store: InMemoryTelemetryStore,
    clock: FixedClock,
    ids: SequentialIdFactory,
) -> TelemetryRecorder:
    return TelemetryRecorder(
        telemetry_store,
        clock=clock,
        ids=ids,
        environment=Environment.PRODUCTION,
        population=Population.OBSERVED,
    )


class RecordingGenerator:
    """A generator that records whether it was called.

    Several tests assert that generation *never happens* on a refusal path.
    Inferring that from an empty answer would pass for the wrong reason, so the
    fact is recorded directly.
    """

    def __init__(self, answer: str = "An approved code review remains valid for 14 days.") -> None:
        self.answer = answer
        self.calls = 0

    def __call__(self, question: str, evidence: EvidenceSet) -> str:
        self.calls += 1
        return self.answer

    @property
    def invoked(self) -> bool:
        return self.calls > 0


@pytest.fixture
def generator() -> RecordingGenerator:
    return RecordingGenerator()


@pytest.fixture
def supported_claims() -> tuple[dict[str, object], ...]:
    return (
        {
            "text": "An approved code review remains valid for 14 calendar days",
            "verdict": "SUPPORTED",
            "evidence_ref": "hb-cr-004",
        },
    )


@pytest.fixture
def make_service(
    registry: ContractRegistry,
    decision_store: InMemoryDecisionStore,
    recorder: TelemetryRecorder,
    clock: FixedClock,
    ids: SequentialIdFactory,
    generator: RecordingGenerator,
):
    """Build a TrustService with overridable parts."""

    def _build(
        *,
        verifier=None,
        authorizer=None,
        gen=None,
        rec=None,
        environment: Environment = Environment.PRODUCTION,
        population: Population = Population.OBSERVED,
    ) -> TrustService:
        return TrustService(
            registry,
            authorizer=authorizer or DeterministicAuthorizer(),
            verifier=verifier or ScriptedVerifier(),
            generator=gen or generator,
            store=decision_store,
            recorder=rec or recorder,
            clock=clock,
            ids=ids,
            environment=environment,
            population=population,
        )

    return _build


@pytest.fixture
def make_request():
    """Build a TrustRequest with sensible synthetic defaults."""

    def _build(
        actor: Actor,
        *,
        resource: str = "handbook/code-review",
        question: str = "How long does an approved code review stay valid?",
        contract_version: str = "1.0",
    ) -> TrustRequest:
        return TrustRequest(
            correlation_id="corr-test-1",
            actor=actor,
            resource=resource,
            question=question,
            contract_id=CONTRACT_ID,
            contract_version=contract_version,
        )

    return _build


@pytest.fixture
def transition_log() -> InMemoryTransitionLog:
    return InMemoryTransitionLog()


@pytest.fixture
def state_machine(
    contract: TrustContract,
    transition_log: InMemoryTransitionLog,
    clock: FixedClock,
    ids: SequentialIdFactory,
) -> LifecycleStateMachine:
    return LifecycleStateMachine(contract, transition_log, clock=clock, ids=ids)
