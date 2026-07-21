# Paper-to-Code Traceability

A reviewer should be able to move from a sentence in the paper to a contract
rule, to the code that enforces it, to the test that pins it, to the evaluation
case that exercises it.

This matrix is **generated** from `contracts/executable-trust-v1.0.yaml` and a
scan of `tests/`. It is not maintained by hand, because a hand-maintained
traceability document is precisely the kind of artifact that drifts from the
system it describes — the failure the paper is about.

`scripts/validate_traceability.py` fails the build if any rule below has no
test naming it, or if any test names a rule the contract no longer declares.

**Coverage: 38/38 rules mapped to tests.**

## Matrix

### `ET-AUTH-001` — authorization_precedes_retrieval

- **Paper section:** The Trust Layer in a Live Request — identity enforced at the gateway
- **Policy statement:** Authorization is evaluated before retrieval and before generation. A denied request exits before any evidence is read; refusing early is cheaper, s...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `authorization_denied`
- **Source module:** `src/executable_trust/authorization/deterministic.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_gates_and_resilience.py`, `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-CON-001` — unknown_version_fails_closed

- **Paper section:** Layer 1 — Versioned; Layer 4 — Ratified
- **Policy statement:** A request naming a contract version this implementation does not carry is refused. The binary never guesses which rules applied.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `contract_version_unknown`
- **Source module:** `src/executable_trust/contracts/registry.py`
- **Tests:** `contract\test_contract_artifacts.py`, `integration\test_governed_flow.py`
- **Known limitation:** —

### `ET-CON-002` — unratified_contract_cannot_govern

- **Paper section:** Layer 1 — Versioned; Layer 4 — Ratified
- **Policy statement:** Only a contract whose ratification status is `ratified` may govern a decision. Draft, superseded, and expired contracts fail closed.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `contract_not_ratified`
- **Source module:** `src/executable_trust/contracts/registry.py`
- **Tests:** `contract\test_contract_artifacts.py`, `integration\test_governed_flow.py`
- **Known limitation:** Ratification is a contract field, not a recorded governance act in a transactional store.

### `ET-CON-003` — malformed_contract_fails_validation

- **Paper section:** Layer 1 — Versioned; Layer 4 — Ratified
- **Policy statement:** A contract that does not validate against schemas/trust-contract.schema.json cannot be loaded, and no decision may be made under it.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `contract_unresolved`
- **Source module:** `src/executable_trust/contracts/registry.py`
- **Tests:** `contract\test_contract_artifacts.py`
- **Known limitation:** —

### `ET-CON-004` — uncontrolled_reason_code_rejected

- **Paper section:** Layer 1 — Versioned; Layer 4 — Ratified
- **Policy statement:** Every reason code emitted at runtime must be declared in the controlled reason-code set for the governing contract version. An undeclared code is a...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/contracts/registry.py`
- **Tests:** `contract\test_contract_artifacts.py`
- **Known limitation:** —

### `ET-EV-001` — evidence_sufficiency_gate

- **Paper section:** Layer 2 — Runtime Enforcement; 'An Evidence Threshold Becomes Enforcement Logic'
- **Policy statement:** Answer only when retrieved evidence quality clears a minimum bar. The refusal is pre-generation: when the gate fails, the generator is never invoked.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `insufficient_evidence`
- **Source module:** `src/executable_trust/evidence/gate.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** Thresholds are the paper's illustrative values, not production values.

### `ET-EV-002` — evidence_provenance_required

- **Paper section:** Layer 2 — Runtime Enforcement; 'An Evidence Threshold Becomes Enforcement Logic'
- **Policy statement:** Every evidence item must declare a provenance drawn from the permitted set. Evidence with missing or unrecognized provenance is not evidence; the r...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `evidence_provenance_invalid`
- **Source module:** `src/executable_trust/evidence/gate.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** Provenance is a declared string; no source attestation is verified.

### `ET-EVAL-001` — baseline_gate

- **Paper section:** Layer 3 — Independent Measurement
- **Policy statement:** The reference baseline is deterministic: the verifier is a deterministic stub and every expected outcome is human-authored, so any divergence betwe...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/evaluation/runner.py`
- **Tests:** `contract\test_contract_artifacts.py`, `test_repository_invariants.py`
- **Known limitation:** Deterministic suite: no variance band, so it cannot model a probabilistic harness.

### `ET-EVAL-002` — offline_owns_correctness

- **Paper section:** Layer 3 — Independent Measurement
- **Policy statement:** Only the offline harness, holding human-authored ground truth, judges whether a decision was correct. The runtime records what it decided and never...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/evaluation/runner.py`
- **Tests:** `contract\test_contract_artifacts.py`, `test_repository_invariants.py`
- **Known limitation:** —

### `ET-LC-001` — transition_proposed_to_accepted

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** Acceptance requires an attributable review by an accountable human. A promotion carrying no accountable reviewer is rejected at the persistence bou...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-LC-002` — transition_proposed_to_rejected

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** Rejection requires an attributable review by an accountable human. Rejected records are retained, never deleted, so the organization does not repea...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-LC-003` — transition_accepted_to_superseded

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** Supersession is recorded as a new append-only transition referencing the successor decision. The predecessor record is never edited.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-LC-004` — terminal_states_are_permanent

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** No transition leaves a terminal state. A superseded or rejected record is retained as recorded; revisiting the question creates a new record that m...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-LC-005` — undeclared_transition_rejected

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** Any transition not declared above is rejected by the domain and by the persistence boundary.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** —

### `ET-LC-006` — decision_payload_immutable

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** A decision record's payload is immutable once created. Corrections create a superseding record; nothing is mutated in place.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** Immutability is enforced in application code; a production store should enforce it at the data layer.

### `ET-LC-007` — current_state_is_a_projection

- **Paper section:** 'An Approval Workflow Becomes a State Machine'
- **Policy statement:** Current state is computed by folding the ordered transition log. No mutable current-state field is authoritative.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/lifecycle/state_machine.py`
- **Tests:** `unit\test_lifecycle_and_records.py`
- **Known limitation:** Projection is over an in-memory log; no durability or concurrency guarantees.

### `ET-OUT-001` — outcome_grounded_requires_strategy

- **Paper section:** Layer 1 — The Contract as Source of Truth; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A GROUNDED outcome must carry a response strategy of DIRECT or BOUNDED.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/domain/enums.py, verification/models.py`
- **Tests:** `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-OUT-002` — outcome_refused_forbids_strategy

- **Paper section:** Layer 1 — The Contract as Source of Truth; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A REFUSED outcome must not carry a response strategy. Absence is the correct representation; a third "refusal" strategy would duplicate the outcome.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/domain/enums.py, verification/models.py`
- **Tests:** `contract\test_contract_artifacts.py`, `regression\test_documented_failure_modes.py`, `unit\test_decision_function.py`, `unit\test_lifecycle_and_records.py`, `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-OUT-003` — outcome_refused_requires_reason_code

- **Paper section:** Layer 1 — The Contract as Source of Truth; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A REFUSED outcome must carry a controlled reason code drawn from reason-codes-v1.0.yaml. An uncontrolled or absent code fails closed.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/domain/enums.py, verification/models.py`
- **Tests:** `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-RES-001` — degrade_to_conservative_verifier

- **Paper section:** 'A Resilience Policy Becomes a Circuit Breaker'
- **Policy statement:** When the primary verification mechanism's observed fault rate exceeds the threshold, the system escalates to a configured conservative mechanism. T...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/verification/resilience.py`
- **Tests:** `unit\test_gates_and_resilience.py`
- **Known limitation:** Paper-specified mechanism; not a production-observed component.

### `ET-RES-002` — refuse_when_no_verifier_available

- **Paper section:** 'A Resilience Policy Becomes a Circuit Breaker'
- **Policy statement:** If no permitted verification mechanism is healthy, the system refuses. Skipping verification to keep answering is prohibited.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `no_verifier_available`
- **Source module:** `src/executable_trust/verification/resilience.py`
- **Tests:** `integration\test_governed_flow.py`, `regression\test_documented_failure_modes.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** Paper-specified mechanism; not a production-observed component.

### `ET-TEL-001` — capture_fails_open

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** Telemetry capture is secondary to the governed decision. A capture failure is logged and swallowed; the decision is returned unchanged. This is the...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-TEL-002` — population_provenance_required

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** Every telemetry event records the environment it came from and whether it describes observed or synthetic activity. Observed metrics exclude every ...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `integration\test_governed_flow.py`, `regression\test_documented_failure_modes.py`, `unit\test_telemetry_and_metrics.py`
- **Known limitation:** Paper-specified mechanism; not a production-observed component.

### `ET-TEL-003` — store_facts_not_scores

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** Telemetry stores what varies — outcome, strategy, reason code, evidence count, claim counts, verification mechanism, latency, contract version. It ...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `integration\test_governed_flow.py`, `regression\test_documented_failure_modes.py`, `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-TEL-004` — counts_always_visible

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** Counts are never withheld. A consumer can always see how many decisions the window contains.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-TEL-005` — rates_withheld_below_minimum_sample

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** A rate computed from fewer than `minimum_sample` decisions is withheld. The rate key remains present and null, and the payload carries the sample s...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `contract\test_contract_artifacts.py`, `regression\test_documented_failure_modes.py`, `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-TEL-006` — runtime_telemetry_makes_no_quality_claim

- **Paper section:** Layer 5 — Durable Telemetry; Layer 6 — Consumer-Side Honesty
- **Policy statement:** Runtime telemetry describes behavior — what the system decided. Quality — how often decisions were correct — is claimed only by the offline evaluat...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/telemetry/`
- **Tests:** `regression\test_documented_failure_modes.py`, `unit\test_telemetry_and_metrics.py`
- **Known limitation:** —

### `ET-VER-001` — empty_claim_set_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** An empty claim collection never yields a grounded answer. A degenerate verifier response that decomposes an answer into zero claims has verified no...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `empty_claim_set`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `integration\test_governed_flow.py`, `regression\test_documented_failure_modes.py`, `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-002` — missing_verdict_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A claim with no verdict field fails closed. It is never treated as supported.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `missing_claim_verdict`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `regression\test_documented_failure_modes.py`, `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-003` — unknown_verdict_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A claim whose verdict is outside the controlled vocabulary fails closed. Unknown is not a synonym for acceptable.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `unknown_claim_verdict`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-004` — unsupported_or_contradicted_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** If any claim is UNSUPPORTED or CONTRADICTED, the system must not present the answer as fact. The answer is refused, never repaired in place (see am...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `unsupported_claim`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `regression\test_documented_failure_modes.py`, `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-005` — no_supported_claims_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A GROUNDED outcome requires at least one SUPPORTED claim. When no claim is supported, the answer is refused under this code rather than under `unsu...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `no_supported_claims`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-006` — irrelevant_answer_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A truthful statement that does not address the question is not an answer. It is refused rather than presented as one.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `does_not_address_question`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-007` — strategy_selection

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A substantive supported answer is GROUNDED. Its strategy is BOUNDED if it states a scope limitation, otherwise DIRECT.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** — (not a refusal rule)
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_decision_function.py`
- **Known limitation:** Strategy depends on a verifier-supplied flag, not on analysis of the answer.

### `ET-VER-008` — malformed_output_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** Verifier output that cannot be parsed into the contract's claim shape fails closed.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `malformed_verifier_output`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `regression\test_documented_failure_modes.py`, `unit\test_decision_function.py`
- **Known limitation:** —

### `ET-VER-009` — verifier_exception_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** Any exception raised by the verification mechanism fails closed. A verifier that fails open is a false sense of safety.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `verifier_error`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** —

### `ET-VER-010` — verifier_timeout_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** A verification call that exceeds its budget fails closed.
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `verifier_timeout`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `integration\test_governed_flow.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** —

### `ET-VER-011` — truncated_output_refuses

- **Paper section:** Layer 2 — Runtime Enforcement; 'A Verification Policy Becomes a Decision Function'
- **Policy statement:** Verifier output cut off at a token or size cap is unusable and fails closed under a reason code distinct from a general error, so telemetry separat...
- **Contract file:** `contracts/executable-trust-v1.0.yaml`
- **Reason code:** `verifier_output_truncated`
- **Source module:** `src/executable_trust/verification/decision_function.py`
- **Tests:** `unit\test_decision_function.py`, `unit\test_gates_and_resilience.py`
- **Known limitation:** —

## Evaluation coverage

The synthetic golden set (`evaluation/golden_set.jsonl`) exercises these rules
end to end. Category-level results are in `reports/reference-baseline.md`.

| Category | Rules exercised |
|---|---|
| `grounded-direct`, `grounded-bounded` | ET-VER-007 |
| `insufficient-evidence` | ET-EV-001 |
| `evidence-provenance-invalid` | ET-EV-002 |
| `unsupported-claim`, `contradicted-claim` | ET-VER-004 |
| `no-supported-claims`, `near-miss` | ET-VER-005 |
| `empty-claim-set` | ET-VER-001 |
| `irrelevant-answer` | ET-VER-006 |
| `malformed-verifier-output` | ET-VER-002, ET-VER-003, ET-VER-008 |
| `verifier-exception` | ET-VER-009 |
| `verifier-timeout` | ET-VER-010 |
| `verifier-output-truncated` | ET-VER-011 |
| `verifier-unavailable` | ET-RES-002 |
| `authorization-denied` | ET-AUTH-001 |
| `unknown-contract` | ET-CON-001 |
| `unratified-contract` | ET-CON-002 |

Rules not exercisable by the request-path harness — the lifecycle rules
(ET-LC-*), the telemetry and metrics rules (ET-TEL-*), the resilience
escalation rule (ET-RES-001), and the artifact-level contract rules (ET-CON-003,
ET-CON-004) — are covered by the unit, contract, and regression suites listed
above.
