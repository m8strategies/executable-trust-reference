# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Version **0.1.0 is released**. Tagged `v0.1.0`, published on GitHub, and
archived on Zenodo with version DOI `10.5281/zenodo.21473597` (concept DOI
`10.5281/zenodo.21473596`). The companion paper is published at
https://www.m8strategies.com/blog/executable-trust.

Licensed under the Apache License, Version 2.0.

## [0.1.0] - 2026-07-21

### Release preparation

- Licensed under the Apache License, Version 2.0. Declared as a PEP 639 license
  expression in `pyproject.toml`; the superseded `License ::` classifier is
  deliberately absent, since setuptools rejects a build carrying both.
- All publication placeholders resolved: repository URL, release tag `v0.1.0`,
  canonical paper URL, and the archive DOI. The DOI was resolved last, since
  Zenodo mints one only after a release is ingested.
- Added `.zenodo.json`. Its title, version, licence, author, keywords, and
  paper relationship are asserted to agree with `CITATION.cff` by test, because
  two files describing one artifact is exactly the shape that drifts.
- Aligned the decision-function guard order across the paper, the contract, the
  implementation, the tests, and the traceability matrix. The order makes
  `empty_claim_set`, `no_supported_claims`, and `unsupported_claim` all
  reachable and distinct; no outcome changes, only the recorded reason code.
- Publication-boundary scanner gained an exact-match mode (`=TERM`).
  Separator-flexible matching is right for a product name, which an author may
  write several ways, and wrong for an upper-snake-case code identifier: flexing
  separators turns such an identifier into an ordinary two-word English phrase,
  which then matches innocent prose. A scanner that cries wolf is one people
  learn to ignore, so identifiers are now matched literally and word-bounded.


Initial reference implementation of the mechanisms described in *Executable
Trust: The Runtime Architecture of Production-Ready Enterprise AI* (Moataz
Mahmoud, M8 Strategies). Everything in this release runs offline: no API keys,
no network access, no database, and no cloud credentials.

### Added

- **Versioned trust contract and reason-code set.** A ratified contract is a
  file, not a convention: `contracts/executable-trust-v1.0.yaml` defines the
  controlled vocabulary, the executable rules, and the thresholds that govern
  every decision, with `contracts/executable-trust-v0.9.yaml` retained as a
  prior version. `contracts/reason-codes-v1.0.yaml` defines the closed set of
  decision-level reason codes. Every executable rule carries a stable
  `ET-XXX-NNN` identifier. Contract resolution is per-decision and status-aware:
  only a ratified, effective contract may govern.
- **Fail-closed decision function.** A pure, deterministic function from
  request, evidence, claims, and resolved contract to an outcome, a response
  strategy, and a reason code. Every path that cannot establish contract
  satisfaction — unresolvable contract, missing or insufficient evidence,
  unsupported or contradicted claims, verifier failure, open circuit — returns
  a refusal with a reason code rather than an unqualified answer. The absence of
  a negative signal is never treated as a positive one.
- **Evidence gate.** Admission and sufficiency checks applied to retrieved
  evidence before any claim is verified, including provenance requirements,
  relevance thresholds, and the coverage test that distinguishes a direct
  grounded answer from a bounded one that states what the evidence does not
  cover.
- **Deterministic verifiers.** Dependency-free claim verifiers producing
  `SUPPORTED`, `UNSUPPORTED`, or `CONTRADICTED` verdicts behind a substitutable
  protocol. Their entailment check is intentionally weak and fully inspectable:
  the architectural claim concerns the machinery around verification, and a
  stronger verifier is a substitution at the protocol boundary rather than a
  change to the design.
- **Circuit breaker.** Resilience wrapper around the verification boundary with
  closed, open, and half-open states. An open circuit fails the decision closed
  with an explicit reason code; it never degrades into permitting unverified
  output.
- **Immutable decision records.** Every decision emits a record carrying the
  contract version in force, the inputs the decision function actually saw, the
  verdicts, the outcome, and the reason code. Records validate against
  `schemas/decision-record.schema.json`, are content-addressed, and the store
  rejects mutation of a recorded decision.
- **Append-only lifecycle with derived state.** Lifecycle transitions are
  appended to a history; current state is derived by folding that history rather
  than stored and overwritten. Illegal transitions are rejected by the state
  machine, and the history is the audit trail.
- **Amendment handling.** Ratified contract versions are immutable. Change is
  expressed as a numbered, dated, attributable amendment under
  `contracts/amendments/`, validated against
  `schemas/contract-amendment.schema.json`, naming the previous and new contract
  versions and preserving the prior version in the tree. A worked example
  amendment ships with the repository.
- **Fail-open telemetry with population provenance.** Telemetry recording never
  blocks or alters a decision; a telemetry failure is absorbed, and events
  recorded on the fail-open path are marked with their provenance so downstream
  populations can be qualified rather than silently treated as complete.
- **Honest metrics with sample-size withholding.** Aggregate metrics disclose
  their population and provenance and withhold rates computed over fewer than
  the configured minimum number of observations, reporting the withholding
  explicitly instead of projecting confidence the sample does not support.
- **Offline evaluation harness with a 27-case synthetic golden set.**
  `evaluation/run_baseline.py` executes `evaluation/golden_set.jsonl` against
  the decision function and writes deterministic reports to `reports/`. Every
  case is synthetic, human-authored, labelled as such, and carries an
  expectation and a contract-grounded rationale written before the code was run.
  A `--check` mode regenerates and compares against the committed baseline so
  that undeclared behavior drift fails the build.
- **Traceability and publication-boundary validation.**
  `scripts/validate_traceability.py` fails the build when any contract rule
  identifier has no test naming it. `scripts/validate_publication_boundary.py`
  fails the build when a private identifier appears in the tracked tree.
  `scripts/validate_contracts.py` validates contracts, amendments, and fixtures
  against the schemas in `schemas/`. All three run in CI, in `make all`, and as
  pre-commit hooks.
- **Project scaffolding.** `Makefile` with a single `all` gate matching CI,
  `.editorconfig`, `.pre-commit-config.yaml`, contribution and security
  policies, a code of conduct, pull request template, code owners, and
  Dependabot configuration.

### Notes

- No license file is present and no license is asserted. License selection is
  deliberately deferred; see `docs/license-options.md`.
- Contract thresholds are reference values chosen for the public artifact. They
  are not production configuration and are not recommendations.
- All fixtures, actors, organizations, and policy texts are synthetic.

[Unreleased]: https://github.com/m8strategies/executable-trust-reference

[0.1.0]: https://github.com/m8strategies/executable-trust-reference/releases/tag/v0.1.0
