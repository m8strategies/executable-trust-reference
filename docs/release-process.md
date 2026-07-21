# Release Process

## Current status

| Step | State |
|---|---|
| Apache-2.0 applied (`LICENSE`, `pyproject.toml`, `CITATION.cff`, `.zenodo.json`) | Done |
| Paper and repository guard order aligned | Done |
| Repository URL resolved | Done — `https://github.com/m8strategies/executable-trust-reference` |
| Release tag resolved | Done — `v0.1.0` |
| Canonical paper URL resolved | Done — `https://www.m8strategies.com/blog/executable-trust` |
| `.zenodo.json` added and reconciled with `CITATION.cff` | Done (asserted by tests) |
| Extended private boundary scan | Done — 70 terms, clean |
| Pushed, CI verified green | Done |
| Publication landing page complete | **Pending** — see criteria below |
| Zenodo enabled, release created, DOI minted | Pending |
| DOI written back into repository, paper, and landing page | Pending |
| Final publication audit from an external reader's perspective | Pending |

`python scripts/validate_release_metadata.py` passes. The DOI gate,
`--require-doi`, reports 9 unresolved `{{ARCHIVE_DOI}}` occurrences and is the
post-archive check.

## Publication landing page criteria

The canonical page is the publication *landing page*, not the paper. The paper
is delivered as a downloadable PDF. Rendering the full body as HTML is not
required.

The page is considered complete when it carries:

- Paper title
- Author
- Executive summary
- Download PDF
- Link to the GitHub reference implementation
- Citation guidance
- Keywords
- M8 Strategies attribution

The reason this gates Zenodo rather than following it: the archived record
declares `isSupplementTo` the canonical page, and a DOI is permanent. The
relationship should resolve to a complete landing page from the moment it is
minted.

## Ordering constraint

Zenodo only archives releases from repositories enabled **beforehand**. Enable
the repository first; a tag created before enabling will not be ingested and
would have to be deleted and recreated.

## Pre-release state

The repository is currently pre-release, and several values that only exist once
a release exists are held as explicit placeholders:

| Placeholder | Resolved when |
|---|---|
| `https://github.com/m8strategies/executable-trust-reference` | The public repository is created |
| `v0.1.0` | The first release is tagged |
| `https://www.m8strategies.com/blog/executable-trust` | The paper has a stable public location |
| `{{ARCHIVE_DOI}}` | The tagged release has been deposited with an archive |

These are unresolved **by design**, not by oversight. A placeholder is visible,
greppable, and machine-checkable. The alternative — a plausible-looking URL, a
guessed tag, or an invented DOI written now and corrected later — is the failure
mode this convention exists to prevent, because a wrong-but-plausible identifier
survives review in a way `https://github.com/m8strategies/executable-trust-reference` never does.

The consequence is a deliberate split in what the checks assert:

- **Ordinary CI passes.** `make all` runs lint, format-check, typecheck,
  contract validation, traceability, publication-boundary, tests, and
  baseline-check. All of it passes with placeholders present, because
  placeholders are the correct working state.
- **Release validation fails.** `python scripts/validate_release_metadata.py`
  exits non-zero and lists every item blocking release. That failure is the
  control: it is what prevents tagging, archiving, or citing an incomplete
  artifact.

Do not "fix" the release gate by resolving a placeholder to something
provisional. The gate failing is the gate working.

## The release gate

`python scripts/validate_release_metadata.py` performs five checks.

1. **No unresolved placeholders.** Every tracked text file is scanned for
   double-brace placeholder tokens. `REPOSITORY_URL`, `RELEASE_TAG`, and
   `CANONICAL_PAPER_URL` block release unconditionally. `ARCHIVE_DOI` is gated
   separately behind `--require-doi`, for the reason below. The validator
   excludes itself by name — it necessarily contains the placeholder pattern in
   order to search for it — and excludes `.private/`, which is gitignored and
   never published.

2. **`CITATION.cff` exists, parses, and is complete.** The file must be valid
   YAML containing a mapping, must declare at least one author, and must carry
   `cff-version`, `title`, `authors`, `message`, `repository-code`, and
   `version`. This is what makes the artifact citable; a paper that references a
   repository the reader cannot cite has not really published it.

3. **Paper references resolve to real repository paths.** The paper is read from
   beside the repository and every repository-relative path it cites in
   backticks — under `src/`, `docs/`, `contracts/`, `schemas/`, `evaluation/`,
   `tests/`, `scripts/`, or `reports/` — is checked to exist. A citation to a
   path that was renamed after the paper was drafted is a broken reference in a
   published document, and it is far cheaper to catch here. If the paper is not
   present beside the repository, this check is **skipped rather than failed**:
   the repository must remain independently valid for someone who has only
   cloned it.

4. **Committed baseline reports are current.** The validator re-runs
   `evaluation/run_baseline.py --check`, which recomputes the reports in memory and
   compares them against what is committed. Because reports are required to be
   byte-for-byte reproducible — no run-time timestamps, no randomness, no
   unordered iteration reaching serialized output, no absolute paths or
   environment-derived values — a discrepancy means either the behavior moved
   without the reports being regenerated, or a report is nondeterministic.
   Both must be resolved before release.

5. **A licence decision has been recorded.** If a `LICENSE` file is present, the
   check passes. If none is present but `docs/license-options.md` is, the
   validator reports the repository as unlicensed and blocks release, naming the
   deferral as deliberate and unresolved. If neither exists, the licence
   decision is undocumented, which is worse. This is why licence selection is
   step one of the sequence below.

## Release sequence

Steps are ordered by dependency. Each one unblocks the next; running them out of
order produces either a wrong value committed to the tree or a gate that cannot
be satisfied.

### 1. The owner selects a licence and adds it

No licence is currently applied, which means the work is "all rights reserved"
by default under copyright law. `docs/license-options.md` compares the options
without recommending one; the choice is the owner's and no other step in this
process can be completed on its behalf.

Add the chosen licence as a `LICENSE` file at the repository root, and set the
`license` field in `pyproject.toml`, which is currently omitted deliberately
with a comment explaining why. Note the constraint recorded in
`CONTRIBUTING.md`: contributions have been accepted on the understanding that a
licence has not yet been chosen and that one will be applied to the repository,
including previously merged contributions, once selected.

This is first because two later steps depend on it — the release gate's licence
check, and archives that require an open licence in order to mint a DOI.

### 2. Create the repository and resolve `https://github.com/m8strategies/executable-trust-reference`

Create the public repository, then replace every occurrence of
`https://github.com/m8strategies/executable-trust-reference` with its canonical URL. Occurrences include `SECURITY.md`
(the private advisory form), `CITATION.cff` (`repository-code`), and any
documentation that links to the repository. Resolve them in one change so no
file is left half-resolved.

Run `python scripts/validate_publication_boundary.py` before the first push. It
runs in `make all` and as a pre-commit hook, but the push that makes the
repository public is the point at which a boundary violation stops being
reversible.

### 3. Resolve `https://www.m8strategies.com/blog/executable-trust`

Replace every occurrence with the paper's stable public location. Do this only
once that location is stable and will not be superseded — a canonical URL that
later moves is worse than a placeholder, because nothing will flag it.

### 4. Regenerate the baseline and commit it

Run:

```
python evaluation/run_baseline.py          # regenerate (writes reports/)
```

This rewrites `reports/reference-baseline.md` and
`reports/reference-baseline.json`, both labelled "Reference implementation
synthetic baseline" and carrying their scope statement in the opening
paragraph. Commit the regenerated reports.

Verify with `python evaluation/run_baseline.py --check`, which must exit zero
against the committed files. Never hand-edit a file under `reports/`; the report
is generated output, and an edited report breaks the determinism guarantee that
makes it worth publishing.

### 5. Run the release validator

```
python scripts/validate_release_metadata.py
```

It must print `release metadata is complete` and exit zero. If it lists blocking
items, resolve them and re-run. Do not proceed to a tag while any item remains:
a tag is the first irreversible step, because a tag is what other people cite.

Also confirm `make all` still passes. The two gates cover different things and
neither substitutes for the other.

### 6. Tag `v0.1.0`

Create the release tag, resolving `v0.1.0` wherever it appears —
including the supported-versions table in `SECURITY.md`, which currently states
that no tag exists — and set `version` in `CITATION.cff` and `pyproject.toml` to
match. Record the release in `CHANGELOG.md`.

The tag and the package version must agree. A citation resolves to a tag; a
dependency resolves to a version; a reader who finds them disagreeing cannot
tell which artifact the paper's numbers came from.

### 7. Archive the release and resolve `{{ARCHIVE_DOI}}`

Deposit the tagged release with an archive service to obtain a DOI, then replace
every `{{ARCHIVE_DOI}}` occurrence — including the `doi` field in
`CITATION.cff` — and re-run:

```
python scripts/validate_release_metadata.py --require-doi
```

**Why the DOI is gated separately.** A DOI is minted by an archive service
*after* a release exists to deposit. Requiring it unconditionally would make the
first release impossible: the gate would demand an identifier that cannot exist
until the gate has already been passed. The `--require-doi` flag is the explicit
second pass, run once the circular dependency has been broken by the tag in step
six.

Note that some archive services require an open licence before they will accept
a deposit. If that applies, the choice made in step one determines whether this
step is available at all.

### 8. Produce `executable-trust.release.md`

The working paper, `executable-trust.md`, **retains its placeholders**. It is
the editable source and it stays that way; resolving placeholders in it would
destroy the property that makes the release gate meaningful, and would silently
diverge the working copy from what was published.

The release variant, `executable-trust.release.md`, is **generated** from the
working paper with every placeholder substituted by its resolved value. It is
never hand-edited. A hand-edited release variant is a second source of truth for
the paper's text, and the first time the two disagree there is no way to tell
which is correct.

Generate it only **after** `python scripts/validate_release_metadata.py
--require-doi` passes. Producing it earlier bakes an unresolved or provisional
value into the document that carries the paper's canonical citation.

## Summary of ordering constraints

- Licence before the release gate can pass, and before an archive deposit that
  requires one.
- Repository URL before citation metadata is complete.
- Baseline regenerated and committed before validation, because validation
  re-runs it.
- Validation before the tag, because the tag is the first irreversible step.
- Tag before the archive, because a DOI is minted against a release.
- DOI before the release variant of the paper, because the variant carries it.
