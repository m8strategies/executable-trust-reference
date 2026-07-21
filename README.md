# Executable Trust — Reference Implementation

Companion artifact to ***Executable Trust: The Runtime Architecture of
Production-Ready Enterprise AI*** by Moataz Mahmoud, M8 Strategies.

| Artifact | Role | Location |
|---|---|---|
| **Paper** | Specification and research argument. The authoritative publication. | [https://www.m8strategies.com/blog/executable-trust](https://www.m8strategies.com/blog/executable-trust) |
| **Repository** | Independent reference implementation of the paper's mechanisms. | [https://github.com/m8strategies/executable-trust-reference](https://github.com/m8strategies/executable-trust-reference) |
| **Zenodo record** | Archived, citable software release. | DOI: `{{ARCHIVE_DOI}}` (minted on release ingest) |

Release: `v0.1.0`

This repository is the companion implementation. It is **not** the canonical
location of the paper; the paper is published at the address above.

---

## Research context

Enterprise AI does not mostly fail on model quality. It fails on everything
around the model: deciding when to trust an output, what to do when it is wrong,
and how to prove any of that to a skeptical stakeholder afterward. In most
organizations that part is a document nobody checks the running system against.

The paper's argument is that the fix is not better documents but a change in
what trust *is* inside a platform.

## Central thesis

**Executable Trust** is enterprise trust implemented as a runtime capability:
something a platform *does* on every request, not something an organization
*writes* about its platform. It is defined by four properties.

| Property | Meaning | Where it lives here |
|---|---|---|
| **Versioned** | The rules carry a version identifier; every behavior change traces to a rule revision | `contracts/`, `schemas/` |
| **Enforced** | The system does not log a violation, it refuses to proceed | `verification/`, `evidence/`, `authorization/` |
| **Independently Measured** | Something outside the enforcement path checks whether it does what it claims | `evaluation/` |
| **Ratified** | A rule change is a deliberate, documented, dated act | `amendments/`, `contracts/amendments/` |

## Relationship to the paper

The paper is the public specification. This repository is one implementation of
it, built so a reviewer can move from a sentence in the paper to a contract
rule, to the code that enforces it, to the test that pins it, to an evaluation
case that exercises it. That path is documented in
[`docs/paper-to-code-traceability.md`](docs/paper-to-code-traceability.md) and
enforced by `scripts/validate_traceability.py`, which fails the build when any
rule has no test naming it.

## Scope

> This repository provides an independent reference implementation of the
> mechanisms described in Executable Trust. Its design is informed by lessons
> from a working production enterprise AI platform, while the implementation,
> examples, contracts, and evaluation data included here are publication-safe
> and independently reproducible. The repository excludes the commercial
> platform, proprietary integrations, production prompts, operational data,
> customer information, and internal deployment architecture.

This is **not** a clean-room implementation, and it is **not** a public copy of
a commercial platform. See [`docs/repository-scope.md`](docs/repository-scope.md).

## Production reference boundary

The reference implementation includes several mechanisms specified by the paper
that extend beyond the production implementation from which some field
observations were drawn. In particular, the reference artifact implements
explicit verification dependency degradation and telemetry population
provenance. These components demonstrate the paper's normative architecture and
must not be interpreted as evidence that every mechanism was operating in the
production system at the time of the reported observations.

Four kinds of evidence appear in this work and must never be conflated:

1. **Production observations** reported in the paper.
2. **Paper-specified normative mechanisms** — architecture the paper argues
   should exist.
3. **Reference implementation behavior** — what this code does when run.
4. **Synthetic evaluation evidence** — results of the golden set against this
   implementation.

The full mechanism-by-mechanism comparison is in
[`docs/production-reference-boundary.md`](docs/production-reference-boundary.md).
Numbers in `reports/` and numbers in the paper measure different systems against
different standards and must never appear in the same comparison.

## What is implemented

- **Versioned trust contract** with ratification status, controlled vocabulary,
  and 38 stable rule identifiers. Two versions ship: `v1.0` (ratified) and
  `v0.9` (draft), the latter existing so the repository can demonstrate — rather
  than assert — that an unratified contract cannot govern a decision.
- **Controlled reason-code set**, cross-checked against the implementation's
  enum in both directions.
- **Fail-closed decision function** over claim verdicts, pure and deterministic,
  with nine distinct refusal codes.
- **Evidence sufficiency and provenance gates**, enforced *before* generation.
- **Deterministic verifiers** behind a Protocol, plus a fault injector that
  makes each fail-closed path reachable.
- **Circuit breaker** that escalates to a conservative mechanism or refuses, and
  never skips verification.
- **Immutable decision records** with supersession by successor reference.
- **Append-only lifecycle log** (`PROPOSED`/`ACCEPTED`/`REJECTED`/`SUPERSEDED`)
  where current state is derived, never stored.
- **Contract amendment process** with three distinct attribution roles and a
  preserved prior version.
- **Fail-open telemetry** with explicit environment and population provenance.
- **Honest metrics**: counts always, rates withheld below the contract's minimum
  sample, and no field that could be read as an accuracy claim.
- **Offline evaluation harness** over a 27-case human-authored synthetic golden
  set, producing byte-reproducible reports.
- **Validation tooling**: contract, traceability, publication-boundary, and
  release-metadata checks.

## What is excluded

Retrieval and generation; real entailment; durable or transactional storage;
production authorization and identity; tenant isolation; secrets management;
observability beyond standard logging; and the contract activation boundary
behaviour described in `docs/architecture.md`. Full list with reasoning:
[`docs/limitations.md`](docs/limitations.md).

## Architecture overview

```
1. Resolve contract   ──► REFUSED  contract_version_unknown | contract_not_ratified
2. Authorize          ──► REFUSED  authorization_denied
3. Evidence gates     ──► REFUSED  evidence_provenance_invalid | insufficient_evidence
4. Generate                        ◄── reached only if 1–3 pass
5. Verify + decide    ──► REFUSED  9 distinct reason codes
6. Record decision (immutable)
7. Capture telemetry (fail-open)
```

Refusals are short-circuits, not error handlers: steps 1–3 exit before the work
they guard, and the tests assert the generator was never called. Enforcement
fails closed; telemetry fails open; reversing either is a design defect. Details
in [`docs/architecture.md`](docs/architecture.md).

### The outcome/strategy relation

`GROUNDED` requires a strategy (`DIRECT` or `BOUNDED`). `REFUSED` forbids a
strategy and requires a controlled reason code. `REFUSED` is an outcome and
deliberately **not** also a strategy — modelling one fact on two axes lets them
disagree. The relation is enforced in the enums, three Pydantic models, three
JSON Schemas, contract validation, and the tests.

The word `verdict` is reserved for claim-level classification
(`SUPPORTED`/`UNSUPPORTED`/`CONTRADICTED`). Decision-level explanations use
`reason_code`.

## Quick start

Requires Python 3.11 or newer. **No API key, no network, no database, and no
cloud credentials.**

```bash
git clone https://github.com/m8strategies/executable-trust-reference
cd executable-trust-reference

python -m venv .venv && . .venv/bin/activate    # Windows: .venv\Scripts\activate
make install                                     # pip install -e ".[dev]"
make all                                         # every check
```

## Example execution

```bash
python examples/run_reference_flow.py
```

This walks one grounded request and each refusal path in turn, printing the
outcome, strategy, and reason code for each, then demonstrates the lifecycle and
the fail-open telemetry guarantee.

### Expected output (abridged)

```
GROUNDED / DIRECT                                  generator invoked: yes
REFUSED  / insufficient_evidence                   generator invoked: no
REFUSED  / authorization_denied                    generator invoked: no
REFUSED  / evidence_provenance_invalid             generator invoked: no
REFUSED  / unsupported_claim                       generator invoked: yes
REFUSED  / contract_not_ratified                   generator invoked: no
```

## Test instructions

```bash
make test        # pytest with coverage, fails under 90%
pytest -q        # plain
pytest -m contract      # contract-artifact tests only
pytest -m regression    # documented failure modes only
```

## Baseline reproduction

```bash
# Verify the committed baseline is current (this is what CI runs, and what a
# reader reproducing the published result should use).
python evaluation/run_baseline.py --check

# Regenerate the committed reports. Only after a deliberate behaviour change,
# and the result must be committed alongside it.
python evaluation/run_baseline.py
```

Reports are byte-identical across runs: no timestamps, no durations, no git
revision, no random identifiers. They are labelled **Reference implementation
synthetic baseline** and carry their own scope note. Exit codes: `0` gate
passed, `1` gate failed, `2` the suite could not run.

## Contract validation

```bash
python scripts/validate_contracts.py            # schema + cross-artifact checks
python scripts/validate_traceability.py         # every rule maps to a test
python scripts/validate_publication_boundary.py # no prohibited identifiers
python scripts/validate_release_metadata.py     # release gate (fails pre-release)
executable-trust rules                          # list rules and reason codes
```

## Amendment process

A contract version is never edited in place. Changing a rule means writing an
amendment under `contracts/amendments/` with three distinct roles (author,
reviewer, ratifier — an author may not ratify their own amendment), a rationale,
the accepted trade-off, and ideally a forward constraint binding the next
implementer. The prior contract file stays on disk so decisions recorded under
it remain explainable.

`contracts/amendments/example-amendment-v1.0-a1.yaml` is the paper's worked
example: refusing a partially supported answer rather than repairing it in
place. See [`docs/governance-model.md`](docs/governance-model.md).

## Traceability

| Artifact | Path |
|---|---|
| Traceability matrix | [`docs/paper-to-code-traceability.md`](docs/paper-to-code-traceability.md) |
| Architecture | [`docs/architecture.md`](docs/architecture.md) |
| Repository scope | [`docs/repository-scope.md`](docs/repository-scope.md) |
| Production reference boundary | [`docs/production-reference-boundary.md`](docs/production-reference-boundary.md) |
| Limitations | [`docs/limitations.md`](docs/limitations.md) |
| Governance model | [`docs/governance-model.md`](docs/governance-model.md) |
| Threat model | [`docs/threat-model.md`](docs/threat-model.md) |
| Release process | [`docs/release-process.md`](docs/release-process.md) |
| License options | [`docs/license-options.md`](docs/license-options.md) |

## Citation

Cite both the software and the paper.

```bibtex
@software{mahmoud_executable_trust_reference,
  author    = {Mahmoud, Moataz},
  title     = {Executable Trust Reference Implementation},
  version   = {0.1.0},
  url       = https://github.com/m8strategies/executable-trust-reference,
  doi       = {{ARCHIVE_DOI}},
  note      = {Companion artifact to \emph{Executable Trust: The Runtime
               Architecture of Production-Ready Enterprise AI}}
}

@techreport{mahmoud_executable_trust,
  author      = {Mahmoud, Moataz},
  title       = {Executable Trust: The Runtime Architecture of
                 Production-Ready Enterprise AI},
  institution = {M8 Strategies},
  type        = {Reference White Paper},
  url         = https://www.m8strategies.com/blog/executable-trust
}
```

Machine-readable metadata is in [`CITATION.cff`](CITATION.cff).

## Security

See [`SECURITY.md`](SECURITY.md). This repository requires no credentials and
stores no secrets; a credential appearing in it is itself a reportable defect.
It is a reference implementation, not a production security control — see
[`docs/threat-model.md`](docs/threat-model.md).

## License

Licensed under the **Apache License, Version 2.0**. The full text is in
[`LICENSE`](LICENSE).

Apache-2.0 was chosen because it grants explicit copyright *and* patent terms,
which matters for an artifact intended for both enterprise and research reuse:
a permissive licence with no patent grant leaves a question a corporate legal
review will ask. [`docs/license-options.md`](docs/license-options.md) records
the options that were compared.

```
Copyright 2026 Moataz Mahmoud, M8 Strategies

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0
```

## Attribution

Authored by **Moataz Mahmoud**, **M8 Strategies**.

Synthetic data notice: every actor, service, document, policy, evidence passage,
question, and result in this repository is fictional and newly authored for
publication. Nothing here is derived from any customer, engagement, or
production corpus.
