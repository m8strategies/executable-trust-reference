# Repository Scope

This document states what this repository is, what it deliberately is not, and
which kinds of evidence it can and cannot support. It is the first thing to read
before citing anything here.

## The scope statement

> This repository provides an independent reference implementation of the
> mechanisms described in Executable Trust. Its design is informed by lessons
> from a working production enterprise AI platform, while the implementation,
> examples, contracts, and evaluation data included here are publication-safe
> and independently reproducible. The repository excludes the commercial
> platform, proprietary integrations, production prompts, operational data,
> customer information, and internal deployment architecture.

That paragraph is the authoritative scope of this artifact. Everything below
elaborates it; nothing below narrows or widens it.

## What Executable Trust means here

The paper defines enterprise trust as a runtime capability rather than a
document, and characterises it by four properties. This repository exists to
make each of the four executable:

| Property | Made concrete by |
|---|---|
| **Versioned** | Trust contracts under `contracts/`, resolved per request; a decision record names the contract version that governed it |
| **Enforced** | The decision function in `src/executable_trust/verification/decision_function.py` and the evidence gate in `src/executable_trust/evidence/gate.py` — refusal, not a logged warning |
| **Independently Measured** | The offline harness in `evaluation/`, which holds human-authored ground truth and is not part of the enforcement path |
| **Ratified** | The amendment mechanism under `contracts/amendments/` and `src/executable_trust/amendments/` — a rule change is a dated, attributable act |

## What is implemented

Every mechanism below runs offline: no API key, no network access, no database,
no cloud credentials. Python 3.11 or later. The only runtime dependencies are
`pydantic`, `PyYAML`, and `jsonschema`.

- **Versioned trust contracts.** `contracts/executable-trust-v1.0.yaml` is the
  ratified contract and the single source of truth for the runtime decision
  function, the offline harness, and the validators. It declares 38 stable rule
  identifiers of the form `ET-XXX-NNN`.
- **Contract resolution that fails closed.** An unknown version refuses under
  `contract_version_unknown`; an unratified version refuses under
  `contract_not_ratified` (ET-CON-001, ET-CON-002). A second contract,
  `contracts/executable-trust-v0.9.yaml`, exists on disk in `draft` status
  precisely so the repository can demonstrate rather than assert that an
  unratified contract cannot govern a decision.
- **Controlled vocabulary, enforced structurally.** Claim verdicts are
  `SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`. Decision outcomes are `GROUNDED`
  and `REFUSED`. Response strategies are `DIRECT` and `BOUNDED` only. `REFUSED`
  is an outcome and never a strategy: a refused decision carries no strategy and
  must carry a controlled `reason_code` (ET-OUT-001 through ET-OUT-003). The
  word *verdict* is reserved for the claim level; decision-level explanation is
  always a reason code.
- **Controlled reason codes.** `contracts/reason-codes-v1.0.yaml` declares every
  code, names the rule that emits it, and records whether the code's name comes
  from the paper or is derived from a fail-closed path the paper describes but
  does not name.
- **An evidence sufficiency gate enforced before generation.** When the gate
  fails, the generator is never invoked (ET-EV-001). Evidence provenance is
  checked first: an item whose origin is unrecognised is not evidence
  (ET-EV-002).
- **Deny-by-default authorization evaluated before retrieval.** A denied request
  exits having read no evidence (ET-AUTH-001).
- **A pure, deterministic, fail-closed decision function.** Guard order is part
  of the contract, not an implementation detail, because reordering changes
  which reason code a request receives and reason codes are the audit surface.
- **Verification dependency degradation.** A rolling health window and a circuit
  breaker that may escalate to a more conservative mechanism or refuse, and is
  never permitted to make the system less verified (ET-RES-001, ET-RES-002).
- **Immutable decision records and an append-only lifecycle.** States are
  `PROPOSED`, `ACCEPTED`, `REJECTED`, `SUPERSEDED`. Transitions are declared;
  undeclared transitions are rejected at the domain and at the persistence
  boundary. Current state is derived by folding the ordered transition log —
  there is no mutable current-state field (ET-LC-001 through ET-LC-007).
- **Telemetry that fails open, with population provenance.** Capture failure is
  swallowed and the decision is returned unchanged (ET-TEL-001), which is the
  exact inverse of the enforcement posture. Every event records its environment
  and whether it is observed or synthetic, so test traffic cannot be aggregated
  into a number claimed to describe production (ET-TEL-002).
- **Honest metrics.** Counts are always visible; rates are withheld below the
  contract's minimum sample and the key remains present and null rather than
  zero; no runtime metric may be named accuracy or correctness (ET-TEL-004
  through ET-TEL-006).
- **An offline evaluation harness.** A 27-case synthetic golden set at
  `evaluation/golden_set.jsonl`, deterministic and with no model provider,
  producing `reports/reference-baseline.md` and `reports/reference-baseline.json`.
- **Self-governing validators.** `scripts/validate_contracts.py`,
  `scripts/validate_traceability.py` (every rule id maps to at least one test,
  in both directions), `scripts/validate_publication_boundary.py`, and
  `scripts/validate_release_metadata.py`.

Entry points: `make all`, `pytest`, `python evaluation/run_baseline.py --check`, and the
four validator scripts.

## What is excluded, and why

| Excluded | Why |
|---|---|
| **The commercial platform** | This repository is not a release, a subset, or a rebranding of any commercial product. No commercial product is named anywhere in it, and a CI scanner enforces that. |
| **Proprietary integrations** | Issue trackers, document systems, and internal APIs are deployment specifics. They add credentials and network dependencies without demonstrating anything about the trust architecture. |
| **Production prompts** | Prompt text is operational intellectual property, is specific to one model and one corpus, and would not be reproducible by a reader. The repository's verifiers are deterministic and readable instead. |
| **Operational data and customer information** | Real corpora, transcripts, and records cannot be published, and anonymisation is not a qualifying exception. Every fixture here is written by hand for this artifact. |
| **Internal deployment architecture** | Hostnames, topologies, network layout, and infrastructure configuration are private and would be a disclosure, not a demonstration. |
| **The retrieval and generation stack** | Embedding models, vector stores, rerankers, and the generator itself are substitutions at a protocol boundary. The generator is a plain callable; the repository is about what surrounds generation, not generation. |
| **Identity provider integration** | Authorization here is a synthetic, role-based, deny-by-default policy over fictional resources. There is no directory, no token validation, and no real principal. |
| **Storage engines** | Decision records and telemetry use in-memory adapters behind narrow protocols. Durability, concurrency, transactionality, and retention are real production concerns and are out of scope; the seam is what transfers, not the adapter. |

Excluding these is not an omission to be filled in later by contribution. A pull
request that introduces a network call, a database, a cloud SDK, or a credential
will be declined — the offline, credential-free property is load-bearing for
reproducibility.

## Four evidence types that must never be conflated

Claims connected to this work belong to exactly one of four categories. They are
not ranked, and none substitutes for another. Mixing them is the category error
the paper warns about: blending *what a system did* with *how often it was
right*, and using whichever number is more convenient.

1. **Production observations reported in the paper.** Things that happened in a
   working enterprise AI platform and were recorded at the time. They live in
   the paper. They can support claims about what occurs in practice and what
   failure modes cost. They are not reproducible from this repository, and
   nothing in this repository evidences them.
2. **Paper-specified normative mechanisms.** Architecture the paper argues
   *should* exist, whether or not any system has yet built it. These support
   claims about what a correct design requires. Some mechanisms implemented
   here — verification dependency degradation and telemetry population
   provenance in particular — belong in this category rather than the first.
3. **Public reference implementation behavior.** What the code in this
   repository does when executed. This supports claims that a mechanism is
   buildable, inspectable, and internally consistent. It says nothing about any
   production system, and nothing about performance under real load.
4. **Synthetic evaluation evidence.** The result of running the human-authored
   golden set against this implementation, recorded in
   `reports/reference-baseline.json` and `reports/reference-baseline.md` and
   labelled "Reference implementation synthetic baseline". A perfect pass rate
   on a deterministic suite against a fictional corpus says the implementation
   conforms to its own contract. It says nothing about how a verifier performs
   on real evidence.

The fourth category is the one most likely to be over-read, which is why the
reports carry their scope statement in the first paragraph rather than in a
footnote. Numbers from `reports/reference-baseline.json` and numbers in the
paper measure different systems against different standards and must never
appear in the same comparison. `docs/production-reference-boundary.md` sets out
the mechanism-by-mechanism boundary in full.

## What this repository is not

- **Not a clean-room implementation.** No attempt has been made, and none should
  be claimed, to build these mechanisms in isolation from prior work. The design
  is informed by lessons from operating a working enterprise AI platform,
  including specific failure modes that platform encountered. That provenance is
  the reason the mechanisms are shaped as they are, and stating it plainly is
  more honest than implying an independence that does not exist.
- **Not a copy, extract, or subset of a commercial platform.** The code,
  contracts, fixtures, thresholds, and evaluation data here were written for
  publication. Contract thresholds are reference values chosen for this
  artifact, not production configuration.
- **Not a production security control.** It is not a content filter, not a
  guardrail product, and not certified or audited for any regulatory regime.
  See `SECURITY.md` and `docs/threat-model.md`.
- **Not a benchmark.** The golden set is a falsification surface for this
  implementation against its own contract. It is not a comparative evaluation of
  verifiers, models, or systems.
- **Not a general-purpose library.** Acceptance criteria are narrower than a
  library's on purpose; see `CONTRIBUTING.md`.

## What can be said

- The mechanisms described in the paper are implementable as inspectable,
  deterministic code.
- The contract, the runtime enforcement path, and the offline harness in this
  repository share a single definition of correct. A disagreement between any
  two of them is a defect, not a difference of opinion.
- The repository's own results are reproducible by anyone, offline, with no
  credentials and no external services.
