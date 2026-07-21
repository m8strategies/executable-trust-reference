# Contributing

Thank you for considering a contribution. Please read this document before
opening a pull request — this repository has narrower acceptance criteria than
a general-purpose library, and the reasons are structural rather than stylistic.

## Scope of contributions

`executable-trust-reference` is a reference implementation accompanying the
paper *Executable Trust: The Runtime Architecture of Production-Ready
Enterprise AI* (Moataz Mahmoud, M8 Strategies). Its purpose is to make the
mechanisms described in the paper executable, inspectable, and falsifiable — not
to be the fastest, most featureful, or most broadly applicable implementation
of any one of them.

The consequence is a hard rule:

> **Every behavior change must trace to a rule in a trust contract.**

If a pull request changes what the system decides, refuses, records, or
reports, there must be a contract rule that says so. If no such rule exists,
the contract change comes first (see *Contract changes* below) and the code
change follows it. Changes that alter behavior without a governing rule will be
asked to add one or be closed.

Contributions that are always welcome, and do not require a contract change:

- Defects — cases where the code disagrees with the contract it claims to
  implement. These are the highest-value contributions.
- Tests that pin existing documented behavior more tightly.
- Documentation that corrects an inaccuracy or removes ambiguity.
- Portability, typing, and tooling fixes that leave behavior identical.

Contributions that will generally be declined:

- New integrations that introduce a network call, a database, a cloud SDK, or a
  credential of any kind. The package is deliberately offline and
  credential-free; that property is load-bearing for reproducibility.
- Features with no counterpart in the paper.
- Performance work that trades away determinism or auditability.

## The four properties

Every mechanism in this repository is evaluated against four properties. A
contribution that weakens any of them needs an explicit argument in the pull
request description.

1. **Governed.** Behavior is determined by a versioned, ratified contract that
   exists as an artifact, not by conventions distributed across the code.
2. **Fail-closed.** When the system cannot establish that an output satisfies
   the contract — missing evidence, an unresolvable contract, a verifier
   failure, an open circuit — it refuses with a reason code. Absence of a
   negative signal is never treated as a positive one.
3. **Auditable.** Every decision produces an immutable record that carries the
   contract version, the inputs the decision function actually saw, and the
   reason code. Records are appended; state is derived from history, never
   overwritten in place.
4. **Honest.** Reported metrics disclose their population and provenance,
   withhold rates below the configured minimum sample size rather than
   projecting confidence they do not have, and mark telemetry that was recorded
   on a fail-open path as such.

## How to add a mechanism

Mechanisms are added in a fixed order. Each step depends on the one before it,
and the validators enforce the order.

1. **Contract rule.** Add the rule to the appropriate file under `contracts/`
   with a stable identifier in the form `ET-XXX-NNN` — a three-letter
   subsystem segment and a zero-padded sequence number (for example
   `ET-OUT-001`). The identifier is permanent: once it exists in a ratified
   contract version, it is never renumbered, reused for different semantics, or
   deleted. Superseding a rule is done by amendment.
2. **Schema.** If the rule introduces or changes a serialized artifact, update
   the corresponding JSON Schema under `schemas/`. Schemas are the contract
   between the runtime and the evaluation harness; both validate against them.
3. **Code.** Implement the rule in `src/executable_trust/`. Prefer adding to the
   subsystem that already owns the concern over introducing a new one. Keep the
   decision path pure and deterministic: no clock reads, no randomness, no I/O.
4. **Test.** Add at least one test that names the rule identifier explicitly —
   in the test function name, a marker, or a docstring, per the convention
   already used in `tests/`. A rule with no test that names it is not
   considered implemented.
5. **Traceability entry.** Run `make traceability`. The validator walks every
   rule identifier in every contract and fails the build if any identifier has
   no test naming it. Contributions do not merge with a traceability gap.

## Running checks locally

```
make install     # editable install with dev extras
make all         # the full gate: lint, format-check, typecheck, contracts,
                 # traceability, boundary, test, baseline-check
```

`make all` is the same sequence CI runs. Run it before opening a pull request.
Individual targets are listed by `make help`.

If a behavior change is intentional and the golden-set results move, regenerate
the baseline reports with `make baseline` and commit the regenerated files in
the same pull request as the change that caused them to move. Never hand-edit a
report under `reports/`.

## Contract changes

A ratified contract version is an immutable artifact. It records what the system
was governed by at a point in time, which is the entire reason decision records
can cite a version and mean something.

- **Never edit a ratified contract version in place.** Not to fix a threshold,
  not to correct a typo in a rule statement, not to add a rule.
- Changes to a ratified contract are made as a numbered amendment under
  `contracts/amendments/`, following the structure of the existing example. An
  amendment is attributable: it names an author, a reviewer, and a ratifier, and
  carries a ratification timestamp.
- An amendment names the previous contract version and the new one. The previous
  version file stays in the tree, unchanged, forever.
- Amendments must validate against `schemas/contract-amendment.schema.json`.

A contract in `draft`, `superseded`, or `expired` status may be edited for
drafting purposes; only `ratified` is frozen.

## Golden set rules

`evaluation/golden_set.jsonl` is the falsification surface for the whole
repository. Its integrity matters more than its size.

- **Every case is synthetic.** Cases are written by hand for this repository.
- **Never add real-world or customer-derived content.** No excerpts from real
  documents, no anonymized production transcripts, no paraphrases of proprietary
  policies, no organization or person that exists. "Anonymized" is not a
  qualifying exception.
- **Label everything synthetic.** Each case carries `"synthetic": true`. Fixture
  files carry a synthetic notice in a header comment.
- **Write the expectation before running the code.** The expected outcome,
  strategy, and reason code are authored from the contract, by a human, and
  committed before the case is executed. A case whose expectation was derived
  from observed output tests nothing; it only records what the code already did.
- Each case carries a `rationale` explaining, in contract terms, why the
  expectation is what it is. Reviewers read the rationale, not the diff of the
  results.
- Cases are named by their discriminating property, not by number alone, so that
  a failure names the behavior that broke.

## Determinism requirement

Reports and records committed to this repository must be byte-for-byte
reproducible from the same inputs, on any machine, in any timezone.

- No timestamps generated at run time in report output. Where a time value is
  semantically required, it is supplied as an explicit input and fixed in the
  fixture.
- No randomness, and no iteration over unordered collections without an explicit
  sort. Set and dict iteration order must not reach serialized output.
- No absolute paths, hostnames, usernames, or environment-derived values in
  reports.
- No wall-clock reads inside the decision function. Time is an argument.

`make baseline-check` regenerates the reports and compares them to what is
committed. A nondeterministic report fails that check on the second run, which
is the intended behavior.

## Publication boundary

This is a public repository extracted from private work. The boundary between
the two is enforced mechanically.

- `scripts/validate_publication_boundary.py` must pass. It runs in CI, in
  `make all`, and as a pre-commit hook.
- **Never add private identifiers.** No product or platform names, internal
  service names, hostnames, repository paths, table or column names, API route
  prefixes, ticket identifiers, or the names of real colleagues or customers.
- The public artifact names the paper, the author, and M8 Strategies. It names
  no commercial product.
- Do not weaken, narrow, or add exclusions to the boundary validator in order to
  make a contribution pass. If the validator flags a term you believe is a false
  positive, say so in the pull request and let a maintainer decide.

## Commit and pull request expectations

- One logical change per pull request. A contract amendment plus its
  implementation plus its tests is one logical change; two unrelated fixes are
  two pull requests.
- Commit messages state what changed and why, in the imperative mood, with the
  contract rule identifier in the body where one applies.
- Fill in the pull request template. The checklist is the review contract.
- Pull requests must be green on `make all` before review, and must include
  regenerated baselines if behavior moved.
- Discussion of design belongs in an issue before a large pull request. A
  mechanism that does not appear in the paper needs agreement on scope first.

## A note on licensing

**No license has been selected for this repository yet.** License selection is
deliberately deferred; the options under consideration are recorded in
`docs/license-options.md`.

Contributions are accepted on the understanding that a license has not yet been
chosen and that one will be applied to the repository, including previously
merged contributions, once selected. If that is not acceptable to you, please
wait until a license is in place before contributing. Do not add license headers
to source files, and do not add a `LICENSE` file in a pull request.
