# Governance Model

This repository governs its own rules by the same mechanism it demonstrates. The
contract is not documentation about the code; it is the artifact the code
implements, and the build fails when the two drift apart.

`CONTRIBUTING.md` states the workflow a contributor follows.
`contracts/amendments/README.md` states the required fields of an amendment.
This document states the model those two enforce, and why each part of it is
shaped as it is.

## The contract is the source of truth

`contracts/executable-trust-v1.0.yaml` is the single source of truth for three
consumers:

1. the runtime decision path in `src/executable_trust/`,
2. the offline evaluation harness in `evaluation/`,
3. the validators in `scripts/`.

All three implement the same document. It follows that if any two of them
disagree about a case, one of them has a **defect** — not a difference of
opinion, not a configuration mismatch, not an area where reasonable people
differ. That reduction is the entire value of having a contract at all: it turns
arguments about intent into bug reports.

Two consequences follow directly.

**Behavior is governed, not conventional.** Every behavior change must trace to
a rule in a contract. If a pull request changes what the system decides,
refuses, records, or reports, and no rule says so, the contract change comes
first and the code change follows it.

**Thresholds live in the contract, not in source.** The evidence gate's minimum
similarity, the metrics minimum sample, the breaker's fault-rate threshold —
each is a contract field. A threshold buried in code is a threshold nobody
reviews, and the people accountable for where the bar sits must be able to see
and change it without reading Python.

A ratified contract version is an immutable artifact. It records what the system
was governed by at a point in time, which is the only reason a decision record
citing a version means anything. It is never edited in place — not to fix a
threshold, not to correct a typo in a rule statement, not to add a rule.

## Stable rule identifiers

Every executable rule carries an identifier of the form `ET-XXX-NNN`: a
three-letter subsystem segment and a zero-padded sequence number. The ratified
contract declares 38 of them across nine subsystems:

| Segment | Concern |
|---|---|
| `ET-OUT` | Outcome and strategy structure |
| `ET-EV` | Evidence sufficiency and provenance |
| `ET-VER` | The verification decision function |
| `ET-AUTH` | Authorization |
| `ET-CON` | Contract resolution |
| `ET-TEL` | Telemetry and metrics |
| `ET-RES` | Verification resilience |
| `ET-LC` | Decision-record lifecycle |
| `ET-EVAL` | Offline evaluation |

An identifier is **permanent**. Once it exists in a ratified contract version it
is never renumbered, never reused for different semantics, and never deleted.
Superseding a rule is done by amendment; the identifier survives so that a
decision record, a test, or an amendment referring to it can still be resolved
years later.

### Every rule maps to at least one test

`scripts/validate_traceability.py` walks every rule identifier in every contract
and fails the build if any identifier has no test naming it. A rule with no test
naming it is not considered implemented, regardless of what the code does.

The validator checks **both directions**, and the second direction matters as
much as the first:

- **No untested rule.** A rule that nothing tests is an assertion, not a
  mechanism.
- **No dangling test.** A test naming a rule that no contract declares passes
  forever without asserting anything. It looks like coverage and is worse than
  no test, because it is coverage nobody re-examines.

The check runs in `make all`, in CI, and is reachable as `make traceability`.
Contributions do not merge with a traceability gap.

## Controlled reason codes

Every decision-level explanation is a reason code drawn from
`contracts/reason-codes-v1.0.yaml`. Each declared code names the rule that emits
it, states the outcome it applies to where one applies, and records its
`origin`: `paper` when the paper names the code, `derived` when the paper
describes the fail-closed path but does not name it. Derived codes additionally
carry a rationale for why they exist as a separate code.

Note the vocabulary boundary this depends on. *Verdict* is reserved for the
claim level — `SUPPORTED`, `UNSUPPORTED`, `CONTRADICTED`. Decision outcomes are
`GROUNDED` and `REFUSED`. A refused decision carries no response strategy and
**must** carry a controlled reason code (ET-OUT-002, ET-OUT-003). These are two
separate semantic axes and the contract keeps them separate structurally, not by
convention.

### Why free text is never an acceptable substitute

A free-text explanation is unaggregatable, unversioned, and untestable.

- **Unaggregatable.** Reason codes are the audit surface. An operator reading
  telemetry needs to distinguish a run of `insufficient_evidence` (a retrieval
  problem) from a run of `unsupported_claim` (a generation problem) from a run
  of `verifier_timeout` (a capacity problem). Free text collapses those into
  strings that no query can group. This is also why the contract splits codes
  that a lazier design would merge: `empty_claim_set` is distinct from
  `no_supported_claims` because a degenerate verifier and a genuinely
  unsupportable answer are different operational problems, and
  `verifier_output_truncated` is distinct from `verifier_error` because capacity
  problems and faults have different owners.
- **Unversioned.** A code is declared in a versioned artifact, so its meaning at
  the time a decision was recorded is recoverable. Free text carries no version
  and no stable meaning.
- **Untestable.** A code maps to a rule, and the rule maps to a test. Free text
  maps to nothing.

Emitting a code that is not declared for the governing contract version is a
contract violation, not a new code (ET-CON-004). The runtime enforces this: the
code enum and the declared set are validated against each other.

**The correct response to a missing code is an amendment.** When a real
situation has no code that fits, that is a genuine gap in the contract and the
gap is closed by adding a declared code through the amendment process — not by
widening an existing code until it means several things, and not by attaching a
sentence of prose to the decision. Reaching for free text at that moment is
precisely how a controlled vocabulary decays into an uncontrolled one.

## The amendment process

An amendment is the fourth property — **Ratified** — made concrete. When the
contract and the implementation disagree, there are three possible responses and
two of them are wrong:

- **Wrong:** change the code to match the document without asking whether the
  document was right. The implementer usually found something real.
- **Wrong:** edit the document to match whatever shipped. That is governance as
  documentation with better formatting, and it leaves no record that a decision
  was ever made.
- **Right:** a numbered, dated amendment stating what changed, why, what
  trade-off is accepted, and what constraint binds whoever touches the code
  next.

Six months on, nobody remembers the reasoning behind a one-line code change.
Everybody can read a dated amendment.

### Three roles, and the author may not ratify

Every amendment names an `author`, a `reviewer`, and a `ratifier`. These are
three roles, and the separation is the point: **authorship is not
ratification**. Someone other than the person proposing the change must review
it, and someone accountable must ratify it. An amendment an author could ratify
alone is a self-approval with extra ceremony, and it would make the ratification
field a formality rather than a control. The same separation appears at the
decision-record layer, where a transition to `ACCEPTED` or `REJECTED` requires
an attributable review by an accountable human and is refused at the persistence
boundary otherwise (ET-LC-001, ET-LC-002).

### Prior versions are preserved, never rewritten

An amendment names `previous_contract_version` and `new_contract_version`. The
previous version file stays in the tree, unchanged, permanently. This is
asserted by the `preserves_prior_version` field and enforced by a test — an
amendment never rewrites the contract it amends. Decisions recorded under the
prior version continue to cite a document that still exists and still says what
it said, which is what makes the citation meaningful.

`compatibility_notes` states whether decisions recorded under the prior version
remain valid or must be re-evaluated. `accepted_trade_off` states what is given
up; an amendment with no cost is usually not being honest about one.
`forward_constraint` is optional but strongly encouraged, because it is what
stops the same loophole reopening in a later implementation.

### Ordering: the contract text is ratified before the code moves

The contract text is permitted to lead the code. The ratification act never
leads the contract text. A system that records an amendment for behavior it does
not yet implement has recorded a plan, not a rule.

Concretely, in order: the rule text changes, it is reviewed, it is ratified, and
only then does the implementation move to match. Reversing this produces the
second wrong response above — an amendment written after the fact to describe
what already shipped, which documents a decision that was never actually made.

## Ratification status, and the draft v0.9 example

Only a contract whose ratification status is `ratified` may govern a decision.
Draft, superseded, and expired contracts fail closed under
`contract_not_ratified` (ET-CON-002).

The repository carries **two contract versions on disk** so this can be
demonstrated rather than asserted:

- `contracts/executable-trust-v1.0.yaml` — status `ratified`. This is the
  governing contract.
- `contracts/executable-trust-v0.9.yaml` — status `draft`, non-governing. It is
  structurally valid and loads successfully. Resolution refuses it: the registry
  raises `ContractNotRatified`, and the request path turns that into a `REFUSED`
  decision carrying `contract_not_ratified`. Its rules are otherwise identical
  to v1.0 and generated from it so the two cannot drift, because the point of
  the file is its status field, not its rules.

A draft contract describes an intention. Only a ratified one is a rule. A
contract in `draft`, `superseded`, or `expired` status may be edited freely for
drafting purposes; only `ratified` is frozen.

`contracts/amendments/example-amendment-v1.0-a1.yaml` is the paper's worked
example — refusing a partially supported answer rather than repairing it in
place. It is synthetic and deliberately **not** applied to v1.0, whose
`amendments` list is empty. That lets the repository exercise both the amendment
structure and the prior-version-preservation invariant without forking the
contract set.

## How to change a rule

Step by step. Each step depends on the one before it, and the validators enforce
the order.

1. **State the problem in contract terms.** Which rule identifier is wrong,
   missing, or under-specified, and what does the current text cause the system
   to do that it should not? If the answer is "the code does the wrong thing but
   the rule is right", this is a defect fix, not a rule change — stop here and
   fix the code.
2. **Draft the amendment.** Create a file under `contracts/amendments/`
   following the structure of the existing example. Name the
   `previous_contract_version` and `new_contract_version`, list
   `affected_rule_ids`, and write the `rationale`, `accepted_trade_off`,
   `compatibility_notes`, and — where it applies — the `forward_constraint`.
   Amendments must validate against `schemas/contract-amendment.schema.json`.
3. **Get it reviewed and ratified.** The `author`, `reviewer`, and `ratifier`
   are three roles; the author may not ratify. Record `approved_at` and
   `effective_from`.
4. **Write the new contract version.** Create a new file under `contracts/`
   carrying the new version and its ratification block. Leave the prior version
   file untouched. If the change adds a rule, assign the next unused number in
   the appropriate `ET-XXX` segment; never reuse or renumber an existing one.
5. **Update the schema if the artifact shape changed.** Schemas under `schemas/`
   are the contract between the runtime and the evaluation harness, and both
   validate against them.
6. **Add or update the reason code.** If the rule emits a new controlled code,
   declare it in the reason-code set with its `rule_id`, `origin`, and summary.
7. **Move the code.** Implement the rule in `src/executable_trust/`, in the
   subsystem that already owns the concern. Keep the decision path pure and
   deterministic: no clock reads, no randomness, no I/O.
8. **Add a test that names the rule identifier** — in the test function name, a
   marker, or a docstring, per the convention already used in `tests/`.
9. **Update the golden set if behavior moved.** Write the expected outcome,
   strategy, and reason code from the contract, by hand, *before* running the
   code. A case whose expectation was derived from observed output tests
   nothing.
10. **Run `make all`,** which includes `make contracts`, `make traceability`,
    `make boundary`, and `make baseline-check`. If results moved intentionally,
    regenerate reports with `make baseline` and commit them in the same change.
    Never hand-edit a file under `reports/`.

## What requires an amendment, and what does not

**Requires an amendment:**

- Changing what the system decides, refuses, records, or reports in any case.
- Adding, removing, or changing the meaning of a rule in a ratified contract.
- Adding a controlled reason code, or changing which rule emits one.
- Changing a threshold in a ratified contract — the evidence gate's minimum
  similarity or minimum chunks, the metrics minimum sample, the breaker's fault
  rate or minimum observations, the evaluation gate's minimum pass rate.
- Reordering the verification guards. The order is contractual because it
  determines which reason code a request receives, and reason codes are the
  audit surface, even where every affected path refuses either way.
- Changing the controlled vocabulary: verdicts, outcomes, strategies, lifecycle
  states, or declared transitions.
- Changing the outcome/strategy relation, the fail-closed posture of
  enforcement, or the fail-open posture of telemetry capture.
- Changing which environments or populations may be described as observed.

**Does not require an amendment:**

- Fixing a defect where the code disagrees with the contract it claims to
  implement. The contract already says what should happen; the code is wrong.
  These are the highest-value contributions.
- Adding a test that pins existing documented behavior more tightly.
- Adding a golden-set case that exercises behavior the contract already
  specifies, where the expectation is authored from the contract.
- Refactoring, typing, tooling, and portability work that leaves behavior
  identical.
- Documentation that corrects an inaccuracy or removes ambiguity, provided it
  does not change a rule statement in a ratified contract.
- Editing a contract that is in `draft`, `superseded`, or `expired` status.
- Changing an error message or detail string, provided the reason code is
  unchanged. The code is the governed surface; the detail string is not.

When in doubt, the test is whether a reader of a decision record would be misled
by the change. If a decision recorded before the change and one recorded after
would carry the same contract version but mean different things, it is an
amendment.
