# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately, not as a public issue.

Use the repository's private advisory form:

    https://github.com/m8strategies/executable-trust-reference/security/advisories/new

Include the affected file or module, the version or commit, what an attacker
gains, and the smallest reproduction you have. Reproductions must be synthetic;
do not attach real-world or customer-derived material.

Expect an acknowledgement of receipt, an assessment of whether the report is in
scope, and — for accepted reports — a fix and a public advisory referencing the
release that carries it. Please allow a reasonable period for a fix before
disclosing publicly, and do not test against any third party's systems.

## This repository holds no credentials

The package requires **no API keys, no network access, no database, and no cloud
credentials**. Every code path, test, validator, and evaluation run executes
offline against files in the tree.

It follows that:

- There is no secret in this repository to leak, and no configuration in which a
  secret is expected.
- **A credential appearing anywhere in this repository is itself a reportable
  defect**, regardless of whether it is live, expired, revoked, or fabricated.
  That includes example keys, placeholder tokens that resemble real ones,
  private key material, connection strings with embedded passwords, and
  internal hostnames. Report it through the private advisory form above rather
  than opening a public issue, even if you believe the value is inert.
- The `detect-private-key` pre-commit hook and the `.gitignore` secret patterns
  are defense in depth, not an indication that any such file is expected.

The publication boundary validator (`scripts/validate_publication_boundary.py`)
is a related but distinct control: it guards against private identifiers, not
credentials. A boundary violation is also reportable privately.

## Scope

In scope: defects in the reference implementation in this repository — the
contract loader and validator, the decision function, the evidence gate, the
deterministic verifiers, the circuit breaker, the decision record store, the
lifecycle state machine, the amendment handler, the telemetry recorder and
metrics, the evaluation harness, and the validation scripts. Also in scope:
credential or private-identifier exposure as described above, and any path by
which reading or executing this repository's contents could compromise a
developer's machine.

Out of scope: this is a reference implementation accompanying a research paper.
**It is not a production security control**, not a content filter, not a
guardrail product, and not certified or audited for any regulatory regime. It is
not hardened against adversarial input, denial of service, or untrusted
multi-tenant use. Deploying it as a safety or compliance boundary in a
production system is a deployment decision made outside this repository, and
weaknesses that arise only from such a deployment are not vulnerabilities in the
reference implementation.

Also out of scope: vulnerabilities in third-party dependencies (report those
upstream; open an issue here if a version bump is needed), and issues that
require an attacker to already have write access to the repository or the
developer's filesystem.

## Not vulnerabilities

The following are known, intentional properties. Reports of these will be closed
as working-as-designed.

- **The deterministic verifiers are illustrative, and their entailment check is
  deliberately weak.** They implement a transparent, dependency-free,
  string- and structure-level check so that every verdict in this repository can
  be read and reproduced by hand. They do not perform semantic entailment, do
  not resist paraphrase, and can be defeated by trivially constructed input.
  This is by design: the paper's claim concerns the *architecture* around
  verification — the decision function, the fail-closed posture, the reason
  codes, the record — not the strength of any particular verifier. A stronger
  verifier is a substitution at the protocol boundary, not a change to the
  architecture. Demonstrating that a crafted string fools a verifier is
  therefore not a security finding.
- **Refusal is the failure mode, and refusals are expected.** Input that causes
  the system to refuse with a reason code is the fail-closed design operating
  correctly, not a denial of service.
- **Synthetic fixtures contain fabricated people, organizations, and policies.**
  Every case in `evaluation/golden_set.jsonl` and every contract value is a
  reference value authored for this artifact. Resemblance to a real entity is
  not a data exposure.
- **Contract thresholds are reference values, not recommended production
  settings.** Their being unsuitable for a given production system is not a
  defect.
- **Telemetry may be recorded on a fail-open path.** Telemetry failures must not
  block a decision; events recorded that way are marked with their provenance so
  that downstream metrics can disclose it. That is the intended behavior.

## Supported versions

| Version         | Supported |
| --------------- | --------- |
| v0.1.0 | Yes       |
| Older tags      | No        |

Only the most recent published release, `v0.1.0`, receives fixes.
There are no long-term support branches. As of this writing `v0.1.0` is
unresolved: version 0.1.0 has not been released, and no tag exists.

## Licensing note

**License: not yet selected — see `docs/license-options.md`.** The absence of a
license does not alter this policy: reports are welcome and will be handled as
described above.
