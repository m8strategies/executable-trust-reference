## Summary

<!-- What changes, and why. State the contract rule this change serves. -->

## Contract rule

<!-- The governing rule id(s), e.g. ET-OUT-001. If this is a pure fix,
     documentation, or tooling change with no behavior change, write
     "No behavior change" and say what makes that true. -->

Rule id(s):

## Checklist

- [ ] This change traces to a contract rule id, or is explicitly a no-behavior-change fix.
- [ ] Any new or changed rule carries a stable `ET-XXX-NNN` id; no existing id was renumbered, reused, or deleted.
- [ ] Every rule id touched by this change maps to at least one test that names it (`make traceability` passes).
- [ ] `make all` passes locally.
- [ ] If behavior changed, baseline reports were regenerated with `make baseline` and the regenerated files are committed here (never hand-edited).
- [ ] Any contract change is accompanied by a numbered amendment under `contracts/amendments/`; no ratified contract version was edited in place.
- [ ] No private identifiers, internal names, hostnames, or commercial branding were added; `make boundary` passes and the validator's term list was not weakened to make this pass.
- [ ] No license header was added to any file, and no `LICENSE` file was added. License selection is deferred — see `docs/license-options.md`.
- [ ] Any new fixture or golden-set case is fully synthetic, human-authored, labelled `synthetic`, and its expectation was written before the code was run.
- [ ] Reports and records remain deterministic: no run-time timestamps, randomness, unordered iteration, absolute paths, or environment-derived values reach serialized output.

## Reports

<!-- If baselines moved, name the cases that changed and explain in contract
     terms why the new expectation is the correct one. If nothing moved, say so. -->

## Notes for reviewers

<!-- Anything a reviewer should look at first, alternatives considered, or
     open questions. -->
