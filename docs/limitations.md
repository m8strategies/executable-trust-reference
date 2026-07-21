# Limitations

A reference implementation that omits its own gaps fails the standard the paper
sets. This document lists them.

## 1. The verifiers are deterministic and do not perform real entailment

Every verifier shipped here is a pure function. `ScriptedVerifier` returns the
verdicts the evaluation case supplies; `KeywordVerifier` does crude token
containment.

This is deliberate, and it costs something real. The repository demonstrates the
*architecture* of claim-level checking — the narrow interface, the fail-closed
contract, the swappability, the reason-code vocabulary — and demonstrates
nothing about the *difficulty* of entailment, which is the genuinely hard part
of building this in production.

**What this means for the baseline.** The 27/27 result tests whether the
decision function does the right thing *given* verdicts. It does not test
whether verdicts can be produced accurately. Those are different problems and
this repository only addresses the first.

**What a production deployment adds.** An NLI model or an LLM judge behind
`verification/protocol.py`, plus a baseline for the judge itself, plus a policy
for what happens when the judge is upgraded.

## 2. There is no persistence, and no transactional behaviour

Storage is in-memory. Durability, concurrency, crash recovery, and multi-process
consistency are all out of scope. The append-only guarantees are enforced by
Python objects, not by database constraints or triggers.

A production implementation should enforce these at the data layer, because an
invariant held only in application code is bypassed by anyone writing to the
store directly.

## 3. Contract activation boundary semantics are not implemented

See `docs/architecture.md` § *Contract Activation Boundary Semantics*. Ratifying
a new contract version is itself a governed action, which means it can sit on
the boundary between the outgoing and incoming regimes. A naive
current-version lookup produces inconsistent version stamping *during* the
activation itself.

The reference implementation uses file-based contracts and an in-memory
registry, so it cannot reproduce, exercise, or validate this behaviour. It is
documented as a known architectural limitation and a future extension rather
than silently omitted.

## 4. The evaluation harness has no variance, so it cannot model a probabilistic one

Because the verifier is deterministic, the baseline gate requires a perfect pass
rate and any divergence is a defect. A harness driving a probabilistic model
needs machinery this one does not have and cannot demonstrate:

- a variance band, so one noisy run cannot move a baseline;
- reproducibility classification across repeated runs, separating a confirmed
  regression from noise;
- single-variable enforcement, so a comparison where more than the subject
  changed is refused rather than reported;
- write-once promotion decisions with a mandatory rationale.

These are real requirements for a production evaluation programme. Their absence
here is a consequence of determinism, not an argument that they are unnecessary.

## 5. Two mechanisms are paper-specified rather than production-observed

The **circuit breaker** (`verification/resilience.py`) and **telemetry
population provenance** (`telemetry/events.py`) are implemented here because the
paper specifies them. They are not components whose production behaviour the
paper reports field observations for.

`docs/production-reference-boundary.md` gives the full mechanism-by-mechanism
comparison. The short version: implementing a mechanism in a reference artifact
demonstrates that the paper's normative claim is buildable. It does not
demonstrate that it was operating in any production system, and it is not
evidence for any reported production result.

## 6. Retrieval and generation are out of scope

The generator is a callable. There is no retrieval pipeline, no index, no
ranking model, and no reranker. `EvidenceSet.truncated_to` is a sort, not a
search.

The paper's argument is about what surrounds generation, so this is a
scoping decision rather than an oversight — but it does mean the evidence gate
here is tested against relevance scores that a case supplies, never against
scores a retrieval system produced.

## 7. Authorization is a synthetic policy, not an access control

`authorization/` implements deny-by-default role-based checks over invented
actors and resources. There is no identity provider, no token validation, no
session handling, no delegation, and no revocation.

It demonstrates *where* authorization sits in the request path — before
retrieval — which is the architectural point. It is not a security control and
must not be deployed as one.

## 8. Single-tenant, single-process, no isolation

No tenant model, no row-level security, no isolation tests. The paper names
tenant isolation among the things a real platform needs; this repository does
not address it at all.

## 9. The lifecycle covers one axis

Only the paper's decision-record lifecycle (PROPOSED / ACCEPTED / REJECTED /
SUPERSEDED). Real systems usually also have a request or workflow lifecycle with
its own states, owners, and reason codes. The enforcement pattern transfers; the
vocabulary does not.

## 10. Reason codes are controlled but not versioned independently

The controlled reason-code set is versioned alongside the contract. A production
system typically wants some vocabularies to change *without* a contract version
bump — an operational code set governed by its own approval, distinct from the
contract enums that are fixed by the specification. That separation is not
modelled here.

## 11. The golden set is small and its domain is fictional

27 cases over an invented internal-engineering corpus. It covers every
documented failure mode at least once, which is what it was built for, but it is
not large enough to be statistically meaningful about anything and its domain
was chosen for publication safety rather than difficulty.

Golden sets also decay: ground truth encodes the domain as it was when a human
wrote it. This one has no refresh process, because it has no domain that
changes.

## 12. Observability is minimal

Standard library logging, and counters exposed on the telemetry recorder. No
tracing, no metrics export, no SLO monitoring, no alerting. The paper's
operational-targets table describes numbers a platform team should watch; this
repository provides no way to watch them.

## 13. No security hardening

See `docs/threat-model.md`. Notably absent: input sanitisation, prompt-injection
defences, rate limiting, secrets management, and supply-chain verification.

## Summary table

| Area | Status | Where it is discussed |
|---|---|---|
| Claim-level verification architecture | Implemented | `verification/` |
| Real entailment | Not implemented | §1 |
| Durable / transactional storage | Not implemented | §2 |
| Contract activation boundary | Documented, not implemented | §3, `docs/architecture.md` |
| Probabilistic evaluation machinery | Not implemented | §4 |
| Circuit breaker | Implemented (paper-specified) | §5 |
| Telemetry population provenance | Implemented (paper-specified) | §5 |
| Retrieval and generation | Out of scope | §6 |
| Production authorization | Not implemented | §7 |
| Tenant isolation | Not implemented | §8 |
| Request/workflow lifecycle | Out of scope | §9 |
| Independently versioned code sets | Not implemented | §10 |
| Large or evolving golden set | Not implemented | §11 |
| Observability | Minimal | §12 |
| Security hardening | Not implemented | §13 |
