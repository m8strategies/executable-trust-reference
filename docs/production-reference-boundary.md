# Production Reference Boundary

This document exists to prevent a specific misreading: that the mechanisms in
this repository are evidence for the field observations reported in the paper,
or that the paper's observations validate the code here.

They are different kinds of evidence. Conflating them would be exactly the
category error the paper's Layer 6 warns about — blending *what a system did*
with *how often it was right*, and using whichever number is more impressive
where it is needed.

## The statement

> The reference implementation includes several mechanisms specified by the
> paper that extend beyond the production implementation from which some field
> observations were drawn. In particular, the reference artifact implements
> explicit verification dependency degradation and telemetry population
> provenance. These components demonstrate the paper's normative architecture
> and must not be interpreted as evidence that every mechanism was operating in
> the production system at the time of the reported observations.

## Four evidence types

Every claim connected to this work belongs to exactly one of these categories.
They are not ranked, and none substitutes for another.

| Type | What it is | Where it lives | What it can support |
|---|---|---|---|
| **Production observation** | Something that happened in a working enterprise AI platform and was recorded at the time | The paper | Claims about what occurs in practice, and what the failure modes cost |
| **Paper-specified normative mechanism** | An architecture the paper argues *should* exist, whether or not any system has built it | The paper | Claims about what a correct design requires |
| **Reference implementation behavior** | What the code in this repository does when executed | This repository | Claims that a mechanism is buildable, inspectable, and internally consistent |
| **Synthetic evaluation evidence** | Results of running the human-authored golden set against the reference implementation | `reports/reference-baseline.json` | Claims that this implementation conforms to its own contract |

The last row is the one most likely to be over-read. A 27/27 result on a
deterministic suite against a fictional corpus says the implementation does what
its contract says. It says nothing about how a verifier performs on real
evidence, and nothing about any production system.

## Mechanism comparison

| Mechanism | Described in paper | Observed in production | Implemented in reference repo | Evidence type | Limitation |
|---|---|---|---|---|---|
| Versioned trust contract as source of truth | Yes | Yes | Yes | Production observation + reference implementation | Reference contracts are files; production systems typically need transactional storage |
| Fail-closed decision function over claim verdicts | Yes | Yes | Yes | Production observation + reference implementation | Reference verdicts are supplied by the case, not inferred from evidence |
| Empty-claim-set and missing-verdict guards | Yes (Layer 7 defect narrative) | Yes — found by independent review | Yes | Production observation + reference implementation | — |
| Evidence sufficiency gate, pre-generation refusal | Yes | Yes | Yes | Production observation + reference implementation | Reference thresholds are the paper's illustrative values, not production values |
| Refuse rather than repair a partial answer | Yes (amendment narrative) | Yes | Yes | Production observation + reference implementation | — |
| Ratified contract amendment process | Yes | Yes | Yes | Production observation + reference implementation | Reference ratification is a file field, not a recorded governance act in a transactional store |
| Immutable decision records; supersession by successor | Yes | Yes | Yes | Production observation + reference implementation | Reference storage is in-memory; durability and concurrency are out of scope |
| Fail-open telemetry capture | Yes | Yes | Yes | Production observation + reference implementation | — |
| Store facts, not derived scores (no confidence field) | Yes | Yes | Yes | Production observation + reference implementation | — |
| Counts always visible; rates withheld below minimum sample | Yes | Yes | Yes | Production observation + reference implementation | — |
| Runtime telemetry makes no quality claim | Yes | Yes | Yes | Production observation + reference implementation | — |
| Offline evaluation against human-authored ground truth | Yes | Yes | Yes | Production observation + reference implementation | Reference harness is deterministic, so it has no judge variance and needs no variance band |
| Independent measurement catching a regression before merge | Yes | Yes | Not applicable | Production observation only | The reference suite is deterministic; it cannot demonstrate a probabilistic regression |
| **Telemetry population provenance** (production / staging / development / test, observed / synthetic) | Yes (Layer 5) | **No — the defect was observed and the fix deferred** | **Yes** | Paper-specified normative mechanism + reference implementation | Demonstrated here; not evidence of production behaviour |
| **Verification dependency degradation / circuit breaker** | Yes ("A Resilience Policy Becomes a Circuit Breaker") | **No — named as unbuilt in the paper's own honest accounting** | **Yes** | Paper-specified normative mechanism + reference implementation | Demonstrated here; not evidence of production behaviour |
| Lifecycle state machine enforced at the data layer | Yes | Yes, on a different lifecycle axis | Yes, on the paper's decision-record axis | Paper-specified normative mechanism + reference implementation | See "Lifecycle axis" below |
| Contract activation boundary semantics | No | Yes | **No** | Production observation only | Requires a transactional store; see `docs/architecture.md` |
| Identity and access as a first-class system | Yes (honest accounting) | Partially | Reference only (synthetic policy) | Paper-specified normative mechanism | Not a production access control |
| Secrets management, tenant isolation, DR | Yes (honest accounting) | Named as in flight | No | Paper-specified normative mechanism | Out of scope for a reference implementation |

### Reading the two bold rows

Two mechanisms are implemented here that the production system had not built at
the time the paper's observations were drawn. This is not a claim of superiority
and should not be read as one — a reference implementation with no users, no
uptime obligation, and no data has a very different cost structure from a
production platform, and building a circuit breaker in it proves only that the
policy translates into code.

What those two rows *do* establish is that the paper's normative claims are
implementable, which is a weaker and more honest statement than "this is how it
works in production."

### Lifecycle axis

The paper describes a **decision-record** lifecycle: a generated record is
proposed, reviewed by an accountable human, and eventually superseded. This
repository implements exactly that, using the paper's four states.

Production systems generally also carry a *request* or *workflow* lifecycle,
which is a different axis with different states and different owners. This
repository deliberately implements only the paper's axis. The enforcement
pattern — declared transitions, terminal states, attribution on the transition,
refusal at the data layer — is the transferable part.

## What must never be said

- ~~"The repository reproduces the production platform."~~
- ~~"Every repository mechanism has been validated in production."~~
- ~~"The production platform already implements every mechanism in the paper."~~
- ~~"The public repository proves the reported production results."~~
- ~~"The synthetic baseline is comparable to the production baseline."~~

Numbers from `reports/reference-baseline.json` and numbers in the paper measure
different systems against different standards. They must never appear in the
same comparison.

## What can be said

- The mechanisms described in the paper are implementable as inspectable,
  deterministic code.
- The contract, the runtime enforcement, and the offline harness in this
  repository share one definition of correct, and a disagreement between them
  is a defect rather than a matter of opinion.
- The repository's design is informed by lessons from operating a working
  enterprise AI platform, including specific failure modes that platform
  encountered.
- The repository's own results are reproducible by anyone, with no credentials
  and no external services.
