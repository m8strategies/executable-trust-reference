# Contract Amendments

An amendment is how a trust contract changes. It is the fourth property —
**Ratified** — made concrete.

## The rule

When the contract and the implementation disagree, there are three possible
responses. Two of them are wrong.

- **Wrong:** change the code to match the document without asking whether the
  document was right. The implementer usually found something real.
- **Wrong:** edit the document to match whatever shipped. This is governance as
  documentation with better formatting, and it leaves no record that a decision
  was ever made.
- **Right:** a numbered, dated amendment stating what changed, why, what
  trade-off is accepted, and what constraint binds whoever touches the code
  next.

The record is the point. Six months on, nobody remembers the reasoning behind a
one-line code change. Everybody can read a dated amendment.

## Required fields

Every amendment in this directory must carry:

| Field | Why it is required |
|---|---|
| `amendment_id` | Stable identifier, referenced from the contract and the traceability matrix |
| `previous_contract_version` / `new_contract_version` | The version transition, explicit |
| `rationale` | Why the change was made, in prose a reviewer can evaluate |
| `author` / `reviewer` / `ratifier` | Three named roles. Authorship is not ratification |
| `approved_at` / `effective_from` | When it was decided, and when it began to govern |
| `affected_rule_ids` | Which stable rule identifiers change meaning |
| `accepted_trade_off` | What is given up. An amendment with no cost is usually not being honest |
| `compatibility_notes` | Whether decisions recorded under the prior version remain valid |
| `preserves_prior_version` | Asserts the prior contract file is retained, not rewritten |

`forward_constraint` is optional but strongly encouraged: it is what stops the
same loophole reopening in a later implementation.

## Invariants enforced by tests

- The prior contract version file is **preserved on disk**, unmodified. An
  amendment never rewrites the contract it amends.
- Amendment files validate against `schemas/contract-amendment.schema.json`.
- Every `affected_rule_ids` entry names a rule that exists in the contract it
  amends.
- An amendment's `previous_contract_version` must match a contract that exists.

## Ordering

An amendment is ratified **before** the implementation moves. The contract text
is permitted to lead the code; the ratification act never leads the contract
text. A system that records an amendment for behavior it does not yet implement
has recorded a plan, not a rule.

## Contents

- `example-amendment-v1.0-a1.yaml` — the paper's worked example: refusing a
  partially supported answer rather than repairing it in place. Synthetic, and
  deliberately **not** applied to `executable-trust-v1.0.yaml`, so the
  repository can demonstrate both the amendment structure and the
  prior-version-preservation invariant without forking the contract set.
