"""Deterministic verifiers.

The reference implementation ships no model client. Every public example, test,
and evaluation case runs against a verifier that is a pure function of its
inputs, which is what lets the repository claim reproducibility and run with no
API key, no network, and no credentials.

That is a real limitation and it is stated plainly: these verifiers demonstrate
the *architecture* of claim-level checking — the interface, the fail-closed
contract, the swappability — not the *difficulty* of entailment. A production
deployment substitutes an NLI model or an LLM judge behind the same Protocol.
The point of the seam is that doing so changes no caller.

:class:`ScriptedVerifier` is the workhorse: the case supplies the verdicts, so
the harness tests the decision function rather than a model's judgement.
:class:`FaultInjectingVerifier` wraps any verifier to exercise the fail-closed
paths that are otherwise hard to reach on purpose.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from executable_trust.domain.errors import (
    VerifierFailure,
    VerifierTimeout,
    VerifierUnavailable,
)
from executable_trust.evidence.models import EvidenceSet
from executable_trust.verification.models import VerifierResponse


class ScriptedVerifier:
    """Returns the claim verdicts supplied to it.

    Used by the golden set: each case authors the verdicts a correct verifier
    would produce, and the harness then measures whether the *decision
    function* does the right thing with them. This separates two questions that
    are usually tangled — "can the verifier tell?" and "given that it told us,
    did we act correctly?" — and this repository is about the second.
    """

    def __init__(
        self,
        claims: Sequence[Mapping[str, Any]] = (),
        *,
        answers_question: bool | None = True,
        truncated: bool = False,
        latency_ms: int = 12,
        name: str = "scripted-deterministic",
    ) -> None:
        self._claims = tuple(claims)
        self._answers_question = answers_question
        self._truncated = truncated
        self._latency_ms = latency_ms
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def healthy(self) -> bool:
        return True

    def verify(self, answer: str, evidence: EvidenceSet, question: str) -> VerifierResponse:
        return VerifierResponse(
            mechanism=self._name,
            claims=self._claims,
            answers_question=self._answers_question,
            truncated=self._truncated,
            latency_ms=self._latency_ms,
        )


class KeywordVerifier:
    """A crude but genuinely evidence-dependent verifier.

    Decomposes an answer on sentence boundaries and marks a sentence SUPPORTED
    when its significant words all appear in some evidence item. It is not good
    entailment and is not offered as any — it exists so the examples show a
    verifier whose verdicts actually depend on the evidence, rather than only
    the scripted one.

    A sentence that mentions a scope limitation is flagged, which is what drives
    BOUNDED strategy selection downstream.
    """

    _SCOPE_MARKERS = ("does not cover", "outside the scope", "not addressed", "no guidance")
    _STOPWORDS = frozenset(
        [
            "a",
            "an",
            "the",
            "is",
            "are",
            "was",
            "were",
            "be",
            "been",
            "being",
            "of",
            "to",
            "in",
            "for",
            "on",
            "at",
            "by",
            "with",
            "and",
            "or",
            "that",
            "this",
            "these",
            "those",
            "it",
            "its",
            "as",
            "from",
            "must",
            "should",
            "may",
            "can",
            "will",
            "shall",
            "not",
        ]
    )

    def __init__(self, name: str = "keyword-deterministic", latency_ms: int = 20) -> None:
        self._name = name
        self._latency_ms = latency_ms

    @property
    def name(self) -> str:
        return self._name

    @property
    def healthy(self) -> bool:
        return True

    def verify(self, answer: str, evidence: EvidenceSet, question: str) -> VerifierResponse:
        sentences = [s.strip() for s in answer.replace("\n", " ").split(".") if s.strip()]
        claims: list[dict[str, Any]] = []

        for sentence in sentences:
            lowered = sentence.lower()
            scope = any(m in lowered for m in self._SCOPE_MARKERS)
            ref = self._entailing_evidence(sentence, evidence)
            claims.append(
                {
                    "text": sentence,
                    "verdict": "SUPPORTED" if ref else "UNSUPPORTED",
                    "evidence_ref": ref,
                    "states_scope_limitation": scope,
                }
            )

        answers_question = bool(claims) and any(
            c["verdict"] == "SUPPORTED" and self._overlaps(question, str(c["text"])) for c in claims
        )
        return VerifierResponse(
            mechanism=self._name,
            claims=tuple(claims),
            answers_question=answers_question,
            truncated=False,
            latency_ms=self._latency_ms,
        )

    def _entailing_evidence(self, sentence: str, evidence: EvidenceSet) -> str | None:
        """Return the id of an evidence item containing every significant word.

        Iterates only over retrieved evidence, so a reference to an item that
        was not retrieved is structurally impossible rather than merely
        unlikely. Dropping a real citation is safe; admitting a fabricated one
        is not.
        """
        words = self._significant(sentence)
        if not words:
            return None
        for item in evidence.items:
            haystack = item.text.lower()
            if all(w in haystack for w in words):
                return item.evidence_id
        return None

    def _overlaps(self, question: str, sentence: str) -> bool:
        q = self._significant(question)
        return bool(q & self._significant(sentence)) if q else False

    def _significant(self, text: str) -> set[str]:
        return {
            w.strip(".,;:()\"'").lower()
            for w in text.split()
            if len(w) > 2 and w.strip(".,;:()\"'").lower() not in self._STOPWORDS
        }


class FaultInjectingVerifier:
    """Wraps a verifier to make a specific fail-closed path reachable.

    Faults are declared by the caller, never random: an evaluation case that
    injects a timeout must inject it on every run, or the baseline stops being
    reproducible.
    """

    #: Behaviours a case may request. ``normal`` delegates untouched.
    BEHAVIORS = (
        "normal",
        "raise",
        "timeout",
        "malformed",
        "truncated",
        "unavailable",
    )

    def __init__(self, inner: Any, behavior: str = "normal") -> None:
        if behavior not in self.BEHAVIORS:
            raise ValueError(f"unknown verifier behavior {behavior!r}; expected {self.BEHAVIORS}")
        self._inner = inner
        self._behavior = behavior

    @property
    def name(self) -> str:
        inner_name: str = self._inner.name
        return inner_name if self._behavior == "normal" else f"{inner_name}[{self._behavior}]"

    @property
    def healthy(self) -> bool:
        return self._behavior not in {"unavailable", "raise", "timeout"}

    def verify(self, answer: str, evidence: EvidenceSet, question: str) -> VerifierResponse:
        if self._behavior == "raise":
            raise VerifierFailure("injected verification fault", reason_code="verifier_error")
        if self._behavior == "timeout":
            raise VerifierTimeout("injected verification timeout")
        if self._behavior == "unavailable":
            raise VerifierUnavailable("injected verifier unavailability")

        if self._behavior == "malformed":
            # A claim whose verdict key is present but outside the controlled
            # vocabulary. Parsing must refuse rather than coerce.
            return VerifierResponse(
                mechanism=self.name,
                claims=({"text": "an assertion", "verdict": "PROBABLY_FINE"},),
                answers_question=True,
                latency_ms=5,
            )

        if self._behavior == "truncated":
            inner: VerifierResponse = self._inner.verify(answer, evidence, question)
            return inner.model_copy(update={"truncated": True, "mechanism": self.name})

        result: VerifierResponse = self._inner.verify(answer, evidence, question)
        return result
