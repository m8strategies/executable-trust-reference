# Reference implementation synthetic baseline

> **Scope.** These results describe this reference implementation's conformance to its own human-authored synthetic golden set, using a deterministic verifier and a fictional evidence corpus. They are not a measurement of any production system, they do not reproduce production performance, and they must not be compared numerically with the field observations reported in the paper.

## Provenance

- **Package version:** `0.1.0`
- **Contract:** `executable-trust-reference` v`1.0` (ratified)
- **Cases:** 27
- **Verifier:** deterministic (scripted); no model provider is used
- **Evidence:** synthetic; a fictional internal-engineering corpus
- **Population:** synthetic / test — never aggregated into observed metrics

## Summary

- **Passed:** 27/27 (100.0%)
- **Failed:** 0
- **Gate:** requires 100% — **PASS**

## By category

| Category | Passed | Total |
|---|---:|---:|
| `authorization-denied` | 2 | 2 |
| `contradicted-claim` | 2 | 2 |
| `empty-claim-set` | 1 | 1 |
| `evidence-provenance-invalid` | 1 | 1 |
| `grounded-bounded` | 2 | 2 |
| `grounded-direct` | 2 | 2 |
| `insufficient-evidence` | 2 | 2 |
| `irrelevant-answer` | 1 | 1 |
| `malformed-verifier-output` | 3 | 3 |
| `near-miss` | 2 | 2 |
| `no-supported-claims` | 1 | 1 |
| `unknown-contract` | 1 | 1 |
| `unratified-contract` | 1 | 1 |
| `unsupported-claim` | 2 | 2 |
| `verifier-exception` | 1 | 1 |
| `verifier-output-truncated` | 1 | 1 |
| `verifier-timeout` | 1 | 1 |
| `verifier-unavailable` | 1 | 1 |

## Cases

| Case | Expected | Actual | Reason code | Generated? | Pass |
|---|---|---|---|:--:|:--:|
| `01-code-review-expiry-direct` | GROUNDED/DIRECT | GROUNDED/DIRECT | `None` | yes | PASS |
| `02-oncall-handover-direct` | GROUNDED/DIRECT | GROUNDED/DIRECT | `None` | yes | PASS |
| `03-retention-bounded-scope` | GROUNDED/BOUNDED | GROUNDED/BOUNDED | `None` | yes | PASS |
| `04-deployment-window-bounded` | GROUNDED/BOUNDED | GROUNDED/BOUNDED | `None` | yes | PASS |
| `05-empty-retrieval-insufficient` | REFUSED | REFUSED | `insufficient_evidence` | no | PASS |
| `06-weak-relevance-insufficient` | REFUSED | REFUSED | `insufficient_evidence` | no | PASS |
| `07-mixed-support-unsupported-claim` | REFUSED | REFUSED | `unsupported_claim` | yes | PASS |
| `08-embellished-detail-unsupported` | REFUSED | REFUSED | `unsupported_claim` | yes | PASS |
| `09-contradicted-severity-claim` | REFUSED | REFUSED | `unsupported_claim` | yes | PASS |
| `10-contradicted-freeze-window` | REFUSED | REFUSED | `unsupported_claim` | yes | PASS |
| `11-all-claims-rejected` | REFUSED | REFUSED | `no_supported_claims` | yes | PASS |
| `12-degenerate-empty-claim-set` | REFUSED | REFUSED | `empty_claim_set` | yes | PASS |
| `13-truthful-but-irrelevant` | REFUSED | REFUSED | `does_not_address_question` | yes | PASS |
| `14-verifier-unknown-verdict` | REFUSED | REFUSED | `unknown_claim_verdict` | yes | PASS |
| `15-verifier-missing-verdict` | REFUSED | REFUSED | `missing_claim_verdict` | yes | PASS |
| `16-verifier-omits-relevance-field` | REFUSED | REFUSED | `malformed_verifier_output` | yes | PASS |
| `17-verifier-raises` | REFUSED | REFUSED | `verifier_error` | yes | PASS |
| `18-verifier-times-out` | REFUSED | REFUSED | `verifier_timeout` | yes | PASS |
| `19-verifier-output-truncated` | REFUSED | REFUSED | `verifier_output_truncated` | yes | PASS |
| `20-no-verifier-available` | REFUSED | REFUSED | `no_verifier_available` | yes | PASS |
| `21-contractor-denied` | REFUSED | REFUSED | `authorization_denied` | no | PASS |
| `22-engineer-denied-architecture-standards` | REFUSED | REFUSED | `authorization_denied` | no | PASS |
| `23-evidence-provenance-invalid` | REFUSED | REFUSED | `evidence_provenance_invalid` | no | PASS |
| `24-unknown-contract-version` | REFUSED | REFUSED | `contract_version_unknown` | no | PASS |
| `25-unratified-draft-contract` | REFUSED | REFUSED | `contract_not_ratified` | no | PASS |
| `26-near-miss-environment-scope` | REFUSED | REFUSED | `no_supported_claims` | yes | PASS |
| `27-near-miss-adjacent-service` | REFUSED | REFUSED | `no_supported_claims` | yes | PASS |
