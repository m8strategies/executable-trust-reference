# Threat Model

This document states what the reference implementation defends against, what it
deliberately does not, and which design decisions carry security consequences.

It is written for two readers: someone evaluating whether a reported behavior is
a defect or a documented property, and someone considering whether any of this
can be carried into a production deployment. The second reader matters more.
This is a reference implementation accompanying a research paper. It is not a
production security control, and the sections below are as much a list of what a
production deployment must add as they are a list of what is here.

`SECURITY.md` covers reporting and the known-not-a-vulnerability list. This
document covers the reasoning.

## Assets

What is worth protecting in this system, and what it means for each to be
compromised.

**The trust contract** (`contracts/*.yaml`). The versioned document that defines
what a trustworthy output is. It is the single source of truth for the runtime
decision function, the offline harness, and the validators. If the contract can
be changed without that change being visible, versioned, and ratified, every
downstream guarantee is unenforceable — a decision record that cites a contract
version means nothing if the version can be rewritten after the fact.

**Decision records** (`src/executable_trust/decisions/`). The immutable evidence
of what the system decided, on what inputs, under which contract version, with
which reason code. Their value is entirely in being unalterable. A record that
can be edited is not evidence; it is a note.

**The lifecycle transition log** (`src/executable_trust/lifecycle/`). The
append-only history from which the current state of a decision record is
derived. Its integrity is what makes accountability real: each transition to
`ACCEPTED` or `REJECTED` names an accountable human, a role, and a reason code.
An attacker who can append an unattributable transition, or remove one, can
launder a decision into the system as reviewed.

**Telemetry** (`src/executable_trust/telemetry/`). The behavioural record, and
its population provenance. The asset is not merely the events but the
*classification*: which environment they came from and whether they are observed
or synthetic. Contaminating that classification produces a number that is not
false in any individual field yet describes a population nobody intended.

**The evaluation baseline** (`evaluation/golden_set.jsonl`,
`reports/reference-baseline.*`). The independent measurement. Its value depends
on the expectations being human-authored from the contract *before* the code
runs. A golden set whose expectations were derived from observed output records
what the code did and asserts nothing.

## Trust boundaries

Three seams. Everything crossing them is untrusted until it has been checked.

**The request perimeter.** Everything entering the governed path in
`src/executable_trust/decisions/service.py`: the actor and role, the named
contract version, the question, the retrieved evidence, and the verifier's
output. None of it is trusted. The contract version is resolved and refused if
unknown or unratified. Authorization is evaluated before retrieval, so a denied
request exits having read nothing. Evidence provenance is checked before
sufficiency. Verifier output is parsed into the contract's claim shape, and
anything that does not parse, or omits a required field, is malformed output
rather than an implied pass.

**The verifier seam.** The verification mechanism sits behind a narrow protocol
(`src/executable_trust/verification/protocol.py`). Everything the mechanism
returns is untrusted structure: a truncated response, an exception, a timeout, a
zero-claim decomposition, and an unknown verdict string each map to a distinct
controlled reason code and each refuse. The seam is also the substitution point:
a stronger verifier replaces the deterministic one here without any change to
the architecture around it.

**The storage seam.** Decision records and telemetry are written through narrow
protocols with in-memory reference adapters. The append-only guarantee is
expressed *at the boundary* — the store refuses to replace an existing
identifier — rather than being a property callers are trusted to preserve. In a
production deployment this seam is where a database sits, and it is the seam
where the guarantee most often quietly disappears.

## Threats addressed by design

**Unverified output reaching a user.** The decision function is fail-closed at
every exit before the single grounded path. Every failure of the verification
mechanism — exception, timeout, truncation, unparseable output, missing field,
unknown verdict, zero claims — refuses. There is no default value for any
required field, because a default that lets an unchecked claim through is
precisely the fail-open edge the contract exists to prevent. The evidence gate
refuses *before* generation, so an answer that would fail was never produced.

**Unauthorized access to governed evidence.** Authorization is deny-by-default
and is evaluated before retrieval (ET-AUTH-001). A role grants an explicit set
of resource patterns; anything not granted is denied. The denied request exits
before any evidence is read, so a denial cannot leak evidence through timing of
the generation step or through a partially populated response.

**Silent contract and code drift.** Every rule carries a stable identifier and
must map to at least one test naming it; `scripts/validate_traceability.py`
fails the build otherwise, and it checks both directions — a test pinning a rule
that no longer exists passes forever while asserting nothing.
`scripts/validate_contracts.py` validates contracts against the schemas under
`schemas/`. A contract that does not validate cannot be loaded, and no decision
may be made under it (ET-CON-003). Emitting a reason code that is not declared
in the controlled set is a contract violation, not a new code (ET-CON-004).

**Retroactive edits to decision history.** Decision payloads are immutable once
created (ET-LC-006). Corrections create a superseding record rather than
mutating anything in place. Current state is computed by folding the ordered
transition log, and no mutable current-state field is authoritative
(ET-LC-007) — which removes the field an attacker would otherwise flip.
Terminal states are permanent (ET-LC-004), and undeclared transitions are
rejected at the domain *and* at the persistence boundary (ET-LC-005), so the
rule is not merely enforced in an interface that can be bypassed.

**Test traffic contaminating operational metrics.** Every telemetry event
records its environment and whether it describes observed or synthetic activity
(ET-TEL-002). Observed metrics exclude every other population by default, and
the metrics payload reports how many events were excluded and why. The failure
this prevents is not a lie in any field; it is a true-looking aggregate over an
unintended population.

**A dependency outage causing verification to be skipped.** The circuit breaker
may escalate to a configured conservative mechanism, and if no permitted
mechanism is healthy the system refuses under `no_verifier_available`
(ET-RES-001, ET-RES-002). The breaker is permitted to make the system slower or
more conservative. It is never permitted to make the system less verified.
Skipping verification to keep answering is prohibited by the contract, not
merely discouraged by convention.

## Threats explicitly not addressed

Each of these is out of scope. For each: why a reference implementation does not
address it, and what a production deployment must add.

**Prompt injection into evidence content.** Retrieved evidence in this
repository is a synthetic fixture supplied by the case; there is no generator
that could be instructed by it, because generation is a plain callable that the
repository deliberately does not implement. Addressing injection requires a real
model, a real corpus, and a real prompt construction step — all three excluded
by scope. *Production must add:* treating retrieved text as untrusted data
rather than instruction, structural separation of instruction from evidence in
prompt construction, output-side checks that do not themselves consume attacker
text as instruction, and detection of evidence that attempts to alter system
behavior.

**Adversarial evidence poisoning of the governed corpus.** The reference corpus
is fictional and fixed, and the provenance check verifies only that an item
declares an origin from the permitted set. It does not verify that the item is
what it claims to be, or that the corpus it came from has not been tampered
with. *Production must add:* write controls and review on corpus ingestion,
integrity verification of stored evidence, provenance that is cryptographically
or transactionally attested rather than self-declared, and monitoring for corpus
changes that shift refusal rates.

**A compromised or dishonest verifier.** The architecture treats the verifier's
*output* as untrusted structure but treats the verifier itself as an honest
participant: a mechanism that consistently returns `SUPPORTED` for everything
will produce grounded decisions, and nothing in the runtime path detects that.
Detecting it is exactly the job of independent measurement, which is offline and
outside the enforcement path by design. *Production must add:* an offline
harness with human-authored ground truth run on a schedule and as a merge gate,
alerting on distribution shifts in outcome and reason-code mix, an
integrity-verified verifier deployment, and — where the risk justifies it —
a second independent mechanism for sampled cross-checks.

**Denial of service.** Refusal is the designed failure mode, so input that
causes refusal is the system working. There is no rate limiting, no quota, no
admission control, and no bound on caller-supplied input size. A reference
implementation has no availability obligation, and adding these would obscure
the mechanisms the repository exists to show. *Production must add:* rate
limiting and quotas per principal, request and payload size bounds, timeouts and
backpressure on every dependency, and capacity planning that accounts for
verification cost on every request.

**Multi-tenant isolation.** There is one policy, one contract registry, one
store, and no tenant concept anywhere. Introducing tenancy would add a
substantial correctness surface that says nothing about executable trust.
*Production must add:* tenant identity carried through the request path and into
every record, per-tenant contract resolution and policy, storage-level isolation
with enforcement below the application, per-tenant telemetry partitioning so one
tenant's activity never enters another's metrics, and tests that specifically
attempt cross-tenant reads.

**Secrets management.** The package requires no API keys, no database
credentials, and no cloud credentials, so there is nothing to manage. A
credential appearing anywhere in this repository is itself a reportable defect.
*Production must add:* a managed secret store, rotation, least-privilege
credentials per component, and secret scanning in CI — noting that this
repository's `detect-private-key` hook and gitignore patterns are defense in
depth, not a working secrets posture.

**Transport security.** There is no network layer. Nothing here listens, dials,
or serialises to a wire. *Production must add:* authenticated and encrypted
transport for every hop including the verifier call and the storage connection,
certificate validation that cannot be disabled by configuration, and
authentication of the caller at the perimeter rather than trusting a
caller-supplied actor identifier as this reference does.

**Supply-chain integrity of dependencies.** The three runtime dependencies are
`pydantic`, `PyYAML`, and `jsonschema`, pinned to major-version ranges rather
than to hashes. Vulnerabilities in third-party dependencies are reported
upstream, not here. *Production must add:* hash-pinned lockfiles, a
reproducible build, dependency vulnerability scanning with an owner and a
service level for response, provenance attestation for build artifacts, and
review of transitive additions.

## Deliberate design decisions with security relevance

**Enforcement fails closed; telemetry fails open. Reversing either is a
defect.** These are two opposite postures held on purpose. The governed decision
is the product: when it cannot be established that an output satisfies the
contract, the system refuses (ET-VER-001 through ET-VER-011, ET-RES-002).
Telemetry is secondary to the decision: a capture failure is logged and
swallowed, and the decision is returned unchanged (ET-TEL-001). Reversing the
first makes an unverified answer reachable whenever a dependency misbehaves —
the failure the whole architecture exists to prevent. Reversing the second makes
the observability path an availability dependency of the product path, so an
outage in a component that only *watches* the system takes the system down. Each
posture is correct only for its own layer, and a change to either should be
treated as a defect report rather than a preference.

**Deny-by-default authorization, evaluated before retrieval.** A role grants an
explicit set of resource patterns and nothing else. The pattern language
supports only a trailing wildcard, deliberately: a policy language rich enough
to be interesting is a policy language rich enough to be wrong in ways nobody
notices. Placing the check before retrieval means a denial reads no evidence at
all, which is cheaper, safer, and more honest than generating and discarding.

**No configuration flag disables verification.** There is no bypass switch, no
`skip_verification`, no environment variable that turns the decision function
into a passthrough, and no degraded mode that answers without a verdict. This is
the single most important omission in the repository. Such a flag is invariably
added for a good reason — an incident, a latency target, a demo — and is
invariably still set months later. The circuit breaker exists so that the
pressure that would otherwise produce a bypass flag has a legitimate outlet:
escalate to a more conservative mechanism, or refuse.

**Conservative population classification.** Telemetry defaults to excluding
anything not explicitly classified as observed activity in a permitted
environment, and the metrics payload states how many events were excluded. An
event whose provenance is unclear is not counted as production. The asymmetry is
intentional: undercounting produces a number that is too small and visibly so,
while overcounting produces a number that is wrong in a direction that flatters
the system. Related: rates below the contract's minimum sample are withheld as
`null` rather than reported, and `null` is never collapsed to zero — a withheld
rate and a rate of zero are different facts.

## On the deterministic verifiers

The verifiers in `src/executable_trust/verification/deterministic.py` perform a
transparent, dependency-free, string- and structure-level check. They do not
perform semantic entailment, do not resist paraphrase, and can be defeated by
trivially constructed input.

This is by design, and it is not a vulnerability. The weakness buys three
properties the repository needs: every verdict can be read and reproduced by
hand, the baseline is byte-for-byte deterministic on any machine, and the whole
artifact runs with no model provider. The paper's claim concerns the
*architecture around* verification — the decision function, the fail-closed
posture, the controlled reason codes, the immutable record — not the strength of
any particular verifier. A stronger verifier is a substitution at the protocol
boundary and changes nothing structural.

Demonstrating that a crafted string fools a reference verifier is therefore not
a security finding. Demonstrating that a fooled verifier's output reaches a user
*without* a governed decision, a reason code, and a record would be.
