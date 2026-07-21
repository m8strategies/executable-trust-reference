"""The evidence-dependent deterministic verifier.

`KeywordVerifier` exists so the examples can show a verifier whose verdicts
actually depend on the evidence, rather than only the scripted one. It is crude
entailment and is not offered as good entailment — but it is shipped code in a
repository about verification, so it is tested.
"""

from __future__ import annotations

from executable_trust.domain.enums import DecisionOutcome, ReasonCode, ResponseStrategy
from executable_trust.evidence import EvidenceItem, EvidenceSet
from executable_trust.verification import KeywordVerifier, decide

RETENTION = "Build artifacts are retained for 90 days in the artifact store."


def _evidence(*texts: str) -> EvidenceSet:
    return EvidenceSet(
        evidence_set_ref="ev-kw",
        items=tuple(
            EvidenceItem(
                evidence_id=f"e{i}",
                text=text,
                relevance_score=0.9,
                provenance="governed_corpus",
            )
            for i, text in enumerate(texts, start=1)
        ),
    )


def test_supported_sentence_cites_the_entailing_item(contract):
    """ET-VER-007: a sentence contained in an evidence item is SUPPORTED and cited."""
    verifier = KeywordVerifier()

    response = verifier.verify(
        "Build artifacts are retained for 90 days.",
        _evidence(RETENTION),
        "How long are build artifacts retained?",
    )
    decision = decide(response, contract)

    assert decision.outcome is DecisionOutcome.GROUNDED
    assert decision.strategy is ResponseStrategy.DIRECT
    assert decision.claims[0].evidence_ref == "e1"


def test_unsupported_sentence_refuses(contract):
    """ET-VER-005: a sentence no evidence item contains is UNSUPPORTED."""
    verifier = KeywordVerifier()

    response = verifier.verify(
        "Build artifacts are retained for 400 years.",
        _evidence(RETENTION),
        "How long are build artifacts retained?",
    )
    decision = decide(response, contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.NO_SUPPORTED_CLAIMS


def test_citations_only_reference_retrieved_evidence(contract):
    """ET-VER-007: references are constructed by iterating retrieved evidence only.

    A reference to an item that was not retrieved is structurally impossible
    rather than merely unlikely: dropping a real citation is safe, admitting a
    fabricated one is not.
    """
    evidence = _evidence(RETENTION, "Logs are retained for 30 days.")
    verifier = KeywordVerifier()

    response = verifier.verify(
        "Logs are retained for 30 days.", evidence, "How long are logs retained?"
    )
    decision = decide(response, contract)

    retrieved = {item.evidence_id for item in evidence.items}
    cited = {c.evidence_ref for c in decision.claims if c.evidence_ref}

    assert cited <= retrieved
    assert cited == {"e2"}


def test_scope_marker_selects_bounded(contract):
    """ET-VER-007: a stated limitation selects BOUNDED over DIRECT."""
    verifier = KeywordVerifier()
    evidence = _evidence(RETENTION, "The standard does not cover customer exports.")

    response = verifier.verify(
        "Build artifacts are retained for 90 days. The standard does not cover customer exports.",
        evidence,
        "How long are build artifacts and exports retained?",
    )
    decision = decide(response, contract)

    assert decision.outcome is DecisionOutcome.GROUNDED
    assert decision.strategy is ResponseStrategy.BOUNDED


def test_irrelevant_but_supported_answer_refuses(contract):
    """ET-VER-006: grounding alone is not sufficient; relevance is separate."""
    verifier = KeywordVerifier()

    response = verifier.verify(
        "Logs are retained for 30 days.",
        _evidence("Logs are retained for 30 days."),
        "What is the escalation path for a severity-one incident?",
    )
    decision = decide(response, contract)

    assert decision.outcome is DecisionOutcome.REFUSED
    assert decision.reason_code is ReasonCode.DOES_NOT_ADDRESS_QUESTION


def test_empty_answer_produces_an_empty_claim_set(contract):
    """ET-VER-001: nothing to decompose means nothing was verified."""
    verifier = KeywordVerifier()

    response = verifier.verify("", _evidence(RETENTION), "anything")
    decision = decide(response, contract)

    assert decision.reason_code is ReasonCode.EMPTY_CLAIM_SET


def test_verifier_reports_its_own_identity_and_health():
    """Provenance is read structurally, so a mechanism must name itself."""
    verifier = KeywordVerifier(name="kw-test")

    assert verifier.name == "kw-test"
    assert verifier.healthy is True
