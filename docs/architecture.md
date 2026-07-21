# Architecture

## The request path

One governed request, in order. Every exit before the last is a fail-closed
refusal carrying a controlled reason code.

```
                    ┌─────────────────────────────────────────┐
                    │  1. Resolve contract  (ET-CON-001/002)  │──► REFUSED
                    └─────────────────────────────────────────┘   contract_version_unknown
                                      │                            contract_not_ratified
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  2. Authorize        (ET-AUTH-001)      │──► REFUSED
                    └─────────────────────────────────────────┘   authorization_denied
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  3. Evidence provenance   (ET-EV-002)   │──► REFUSED
                    │     Evidence sufficiency  (ET-EV-001)   │   evidence_provenance_invalid
                    └─────────────────────────────────────────┘   insufficient_evidence
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  4. Generate                            │  ◄── only reached here
                    └─────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  5. Verify + decide  (ET-VER-001..011)  │──► REFUSED
                    └─────────────────────────────────────────┘   9 distinct reason codes
                                      │
                                      ▼
                          GROUNDED / DIRECT or BOUNDED
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │  6. Record decision (immutable)         │
                    │  7. Capture telemetry (fail-open)       │  ── ET-TEL-001
                    └─────────────────────────────────────────┘
```

Three properties of this shape carry the weight.

**Refusals are short-circuits, not error handlers.** Steps 1–3 exit before the
work they guard. Generation that never happens cannot be trusted incorrectly,
and refusing early is cheaper than generating an answer and discarding it. The
tests assert this directly: the generator records whether it was called, and
every pre-generation refusal test asserts `calls == 0`.

**One contract feeds three points.** The registry, the decision function, and
the evaluation harness all read `contracts/executable-trust-v1.0.yaml`. If the
runtime and the harness ever disagree on a case, one of them has a defect — not
a difference of opinion, because both claim to implement one document.

**Telemetry follows and cannot lead.** The decision is recorded and final before
capture is attempted. By the time capture runs there is nothing left for it to
influence, which is why a capture failure provably cannot change an outcome.

## Layer map

| Paper layer | Property | Modules |
|---|---|---|
| 1. Contract as source of truth | Versioned | `contracts/`, `schemas/` |
| 2. Runtime enforcement | Enforced | `verification/`, `evidence/`, `authorization/` |
| 3. Independent measurement | Independently Measured | `evaluation/` |
| 4. Change control for the contract | Ratified | `amendments/` |
| 5. Durable telemetry | — | `telemetry/events.py`, `recorder.py`, `store.py` |
| 6. Consumer-side honesty | — | `telemetry/metrics.py` |
| 7. Independent review | — | `traceability/`, `scripts/` |

## Seams

Four Protocols, each existing so a production deployment can substitute a real
implementation without touching any caller.

| Seam | Protocol | Reference adapter | Production substitute |
|---|---|---|---|
| Verification | `verification.protocol.Verifier` | `ScriptedVerifier`, `KeywordVerifier` | NLI model, LLM judge |
| Authorization | `authorization.protocol.Authorizer` | `DeterministicAuthorizer` | Identity provider, policy engine |
| Decision storage | `decisions.store.DecisionStore` | `InMemoryDecisionStore` | Append-only database table |
| Telemetry storage | `telemetry.store.TelemetryStore` | `InMemoryTelemetryStore` | Event stream, WORM store |

The verification seam is the one that earns its keep. Resilience
(`verification/resilience.py`) was added as a *wrapper* implementing the same
Protocol, so the circuit breaker exists without any call site knowing about it.

## The decision function

`verification/decision_function.py` is pure: no I/O, no clock, no model. Given
the same inputs it returns the same decision forever, which makes it testable as
a function and reproducible as a baseline.

Guard order is contract, not implementation detail. Reordering changes which
reason code a request receives, and reason codes are the audit surface.

```
1. truncated output          ET-VER-011  verifier_output_truncated
2. parse claims              ET-VER-002  missing_claim_verdict
                             ET-VER-003  unknown_claim_verdict
                             ET-VER-008  malformed_verifier_output
3. empty claim set           ET-VER-001  empty_claim_set
4. no SUPPORTED claim        ET-VER-005  no_supported_claims
5. any rejected claim        ET-VER-004  unsupported_claim
6. relevance missing         ET-VER-008  malformed_verifier_output
   relevance false           ET-VER-006  does_not_address_question
7. strategy selection        ET-VER-007  → GROUNDED / DIRECT | BOUNDED
```

Two ordering choices are deliberate and worth stating.

**Truncation before parsing.** A truncated response may parse into a *prefix* of
the intended claims. Parsing first would silently drop the unexamined tail —
which is where the unsupported claim most likely was.

**Steps 4 and 5 are ordered so both codes are reachable and distinct.**
Checking "nothing was supported" before "something was rejected" means
`no_supported_claims` denotes a wholly unsupportable answer and
`unsupported_claim` denotes a partly supportable one. Reversed, the second guard
would catch every rejected claim first and the first would be reachable only for
an empty list. No outcome changes — every path here refuses — only the recorded
code. The paper, the contract, and this module state the same order.

## The outcome/strategy relation

Enforced in five places, because a relation enforced in one place is a
convention:

1. `domain/enums.py` — `ResponseStrategy` has exactly two members
2. `verification/models.py` — `VerificationDecision` validator
3. `decisions/records.py` — `DecisionRecord` validator
4. `telemetry/events.py` — `TelemetryEvent` validator
5. `schemas/*.json` — `if`/`then` clauses on three schemas

The rule:

- `GROUNDED` **requires** a strategy of `DIRECT` or `BOUNDED`, and forbids a
  reason code.
- `REFUSED` **forbids** a strategy, and **requires** a controlled reason code.

`REFUSED` is deliberately not also a strategy. Modelling it on both axes would
put one fact in two places that can then disagree. The null strategy on a
refusal is not a gap to be filled: no answer was presented, so there was no way
of presenting it.

## Lifecycle

`PROPOSED → ACCEPTED | REJECTED`, and `ACCEPTED → SUPERSEDED`. `REJECTED` and
`SUPERSEDED` are terminal.

The decision record carries **no state field**. Current state is computed by
folding the append-only transition log (`lifecycle/history.py::project_state`),
so there is no field to update incorrectly and nothing that can disagree with
history. `state_at(history, n)` reconstructs the state as of any point.

Attribution lives on the transition, not the record: actor, actor type, role,
reason code, timestamp, and contract version. A transition to `ACCEPTED` or
`REJECTED` requires an actor of type `principal` with a role — a system actor
can never satisfy it, which is what makes "an accountable human reviewed this"
checkable.

Invalid transitions are refused at the domain boundary *and* the log refuses
out-of-order or duplicate sequences at the persistence boundary. A control
merely absent from an interface is bypassed by anyone calling the API directly.

## Telemetry and metrics

Capture is fail-open; enforcement is fail-closed. Stated as inverses because
reversing either is a design defect: a verifier that fails open is a false sense
of safety, and a telemetry write that can break a decision has made the observer
more important than the thing observed.

Telemetry stores facts that vary. There is no `confidence` field, no `accuracy`
field, and no `correct` field — and `extra="forbid"` plus an explicit `not`
clause in `schemas/telemetry-event.schema.json` make adding one a validation
error rather than a code review comment.

Metrics withhold rates below the contract's minimum sample while always
reporting counts, and ship `minimum_sample`, `insufficient_sample`, and a
`quality_note` inside the payload so a consumer can explain a withheld number
instead of rendering a blank.

## Contract Activation Boundary Semantics

**This behaviour is documented, not implemented.** It is recorded here because
it is a genuine architectural problem that any transactional implementation of a
versioned contract will encounter, and omitting it would leave the next
implementer to rediscover it.

Ratifying a new contract version is itself a governed action. It is recorded,
attributed, and — in a transactional system — written inside a transaction. That
creates a boundary case:

- The ratification act writes the record that makes version *N+1* governing.
- Other records written *by that same act* must be stamped with a contract
  version.
- A naive "look up the current governing version" call, evaluated per write,
  returns version *N* before the act's own record lands and version *N+1*
  afterwards.
- The result is a single logical action whose records are stamped with two
  different contract versions — an artifact that is permanently unexplainable,
  because it appears to have been governed by two regimes at once.

**What an implementation must define explicitly:**

1. **Which contract governs the ratification action itself.** The defensible
   answer is that the activating action belongs wholly to the *outgoing* regime,
   and the incoming version takes effect from the next action. The act is the
   last record made under the old rules, not the first under the new ones.
2. **The scope over which version resolution is cached.** Resolution must be
   evaluated once per atomic unit of work and reused within it. Caching more
   broadly reintroduces split-brain between a stale cache and the store; caching
   less broadly reintroduces the split stamping above.
3. **A single stamping point.** Exactly one component should apply the contract
   version to outgoing records, and model-level defaults should be removed so
   that a record bypassing that component fails loudly rather than silently
   receiving a constant.
4. **Gate consistency.** Any predicate of the form "are version *N+1* semantics
   active?" must resolve through the same mechanism that stamps records, so a
   gate can never disagree with the version stamped on records written in the
   same unit of work.
5. **Dedicated persistence and regression tests.** Activation-boundary behaviour
   is exercised once per version and is therefore under-tested by ordinary
   traffic. It deserves tests that specifically span the boundary.

**Why this repository does not implement it.** Contracts here are files and the
registry is an in-memory map. There is no transaction, so there is no boundary
to sit on, and an implementation would be a simulation that could not be
validated against the behaviour it models. Building it would produce code that
looks like a demonstration but proves nothing.

See also `docs/limitations.md` §3.

## Determinism

Reproducibility is claimed, so it is engineered rather than hoped for.

- Clocks and identifier factories are injected (`domain/identifiers.py`).
  `FixedClock` and `SequentialIdFactory` are used by the harness.
- Reports contain no timestamp, no duration, no git revision, and no random
  identifier.
- Evidence ordering is a stable sort with a tie-break on identifier.
- Each evaluation case gets fresh stores and counters, so cases cannot influence
  one another.

`tests/test_repository_invariants.py::test_baseline_is_byte_reproducible` runs
the suite twice and asserts the reports are identical.
