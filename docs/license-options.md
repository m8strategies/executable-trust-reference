# License Options

> **Decision recorded.** This repository is licensed under the **Apache License,
> Version 2.0**. See [`LICENSE`](../LICENSE). Apache-2.0 was selected because it
> provides explicit copyright and patent terms while permitting enterprise and
> research reuse.
>
> The comparison below is retained as the record of what was considered. It is
> the reasoning behind the decision, not an open question.


This document compares four licensing options for this repository. It does not
recommend one.

## The current state, stated plainly

**No licence is applied to this repository.** There is no `LICENSE` file, and
the `license` field in `pyproject.toml` is deliberately omitted with a comment
explaining why.

Under copyright law, the absence of a licence does not place the work in the
public domain and does not imply permission. The default is **all rights
reserved**: others may read the repository, but they have **no permission to
use, copy, modify, or redistribute it**. This applies to the code, the
contracts, the schemas, the evaluation data, and the documentation.

Practical consequences of that default, today:

- A reader may study the implementation and cite the paper. They may not
  incorporate any of this code into their own work, run it as part of a product,
  fork it, or redistribute it.
- Package managers, corporate review processes, and many downstream tools treat
  an unlicensed repository as unusable, often automatically.
- Some archive services will not mint a DOI for an artifact with no open
  licence, which would block the archival step of the release process (see
  `docs/release-process.md`).
- Contributions have been accepted on the understanding, recorded in
  `CONTRIBUTING.md`, that a licence has not yet been chosen and that one will
  later be applied to the repository including previously merged contributions.

The release gate (`scripts/validate_release_metadata.py`) reports the unlicensed
state as a deliberate, documented deferral that must be resolved before public
release. That is the reason this document exists.

## Dependency context

All three runtime dependencies are permissively licensed:

| Dependency | Licence family |
|---|---|
| `pydantic` | MIT (permissive) |
| `PyYAML` | MIT (permissive) |
| `jsonschema` | MIT (permissive) |

Permissive dependencies impose no reciprocal obligation, so they do not
constrain the choice: every option below is compatible with all three. The
obligations that remain are the ordinary ones — retain the dependencies' notices
where the licences require it. Because no dependency is copyleft, there is no
scenario in which a dependency forces this repository to adopt a particular
licence.

---

## Option 1: Apache License 2.0

**What it permits.** Use, modification, distribution, and sublicensing, for any
purpose including commercial, with or without source. Requires that recipients
receive the licence text and the `NOTICE` file if one exists, and that modified
files carry a change notice. It includes an express patent grant from
contributors to users, and a patent-retaliation clause: a user who initiates
patent litigation alleging the work infringes their patents loses their patent
licence under it.

**Academic citation and reuse.** Straightforward. A reader can reproduce
results, fork the repository for their own experiments, publish derived work,
and archive it. Citation is governed by `CITATION.cff` and academic norms, not
by the licence — no licence compels citation, and Apache-2.0 requires
attribution of the licence and notices rather than a citation.

**Contributions from others.** The best-understood position of the four. Apache
-2.0 §5 states that contributions are licensed under the same terms unless
explicitly stated otherwise, which gives inbound rights without a separate
contributor agreement. Corporate contributors are generally cleared to
contribute to Apache-2.0 projects without bespoke legal review.

**Patent position.** The strongest of the four. Contributors grant an express
patent licence for their contributions, so users are not exposed to a
contributor later asserting a patent over code they contributed. The retaliation
clause is a defensive deterrent. This is the reason Apache-2.0 is the default in
corporate open source.

**Dependency compatibility.** Fully compatible with MIT dependencies. Apache-2.0
work can also be combined into GPLv3 projects downstream, which matters only if
you care about that reuse path.

**Signal to a commercial audience.** Reads as professional and enterprise-ready.
Legal teams recognise it instantly and clear it routinely. It signals that the
repository is a genuine open artifact rather than a teaser, and it signals
seriousness about patent hygiene. It does **not** signal that any accompanying
commercial platform is open — the two are separate artifacts — but a reader may
infer that the reference implementation is safe to build on, so anything you do
not want built on should not be in the repository regardless of licence.

---

## Option 2: MIT License

**What it permits.** Effectively everything Apache-2.0 permits, in about two
hundred words: use, copy, modify, merge, publish, distribute, sublicense, and
sell, subject only to retaining the copyright notice and the licence text. No
change-notice requirement, no `NOTICE` file mechanics.

**Academic citation and reuse.** Equally straightforward, and arguably the
lowest-friction option for a reader who wants to lift a module into a paper's
supplementary code. Brevity is a real advantage in an academic context: reviewers
and readers can read the whole licence.

**Contributions from others.** Widely understood and universally cleared. MIT
has no explicit inbound-contribution clause equivalent to Apache-2.0 §5, so
projects that want the inbound terms stated rely on convention or add a short
statement in `CONTRIBUTING.md`. In practice this is rarely a problem for a small
reference repository, and is a real difference at scale.

**Patent position.** Weaker than Apache-2.0. MIT grants no express patent
licence. There is an argument that a patent licence is implied by the grant to
"use" and "sell", but it is not explicit, and there is no retaliation clause.
Some corporate reviewers treat this as a material difference; others do not. If
there is any patent strategy connected to this work, this is the axis on which
MIT and Apache-2.0 differ most.

**Dependency compatibility.** Identical licence family to all three
dependencies, so the combination is as simple as it gets.

**Signal to a commercial audience.** Maximally permissive and maximally
frictionless. It signals openness and confidence. It also signals that you are
not attempting to constrain commercial reuse of the reference implementation at
all — which is either exactly the intent or exactly the concern, depending on
how close the reference mechanisms are to what a commercial offering sells.

---

## Option 3: A source-available research licence (non-commercial / research-use-only)

Examples of this family include Creative Commons BY-NC variants for
documentation, the Polyform Noncommercial licence, and bespoke research-use
terms. Details vary considerably between them; what follows is the family's
shared shape.

**What it permits.** Reading, running, modifying, and redistributing for
non-commercial, research, or evaluation purposes, while withholding permission
for commercial use. The definition of "commercial" is the crux and is
notoriously hard to draw: whether an industrial research lab, a consultancy
evaluating the approach, or a company internally piloting the mechanisms falls
inside or outside the grant is often genuinely unclear from the text.

**Academic citation and reuse.** Adequate for reading and reproducing, with
friction. Many university and lab legal policies are cautious about
non-commercial terms because the boundary is ambiguous and because
industry-funded academic work may not qualify. A researcher who wants to build
on the code in a project with any industrial funding may have to seek
permission, and some will simply not bother.

**Contributions from others.** The hardest of the four. Non-commercial licences
are not OSI-approved, so many corporate contribution policies prohibit
contributing to them outright. Outside contributors may also object that they
would be contributing labour under terms that reserve commercial exploitation to
the owner alone. Realistically, this option means fewer contributions, and the
ones that come will need a clear inbound licensing statement.

**Patent position.** Varies by instrument, and several in this family are silent
on patents. If a patent grant matters, it has to be read for specifically rather
than assumed.

**Dependency compatibility.** No conflict with the permissive dependencies —
they impose no reciprocal obligation. But note the asymmetry: this repository's
own code would be under more restrictive terms than everything it depends on,
which some readers will notice and some will find inconsistent with the
repository's stated purpose of being independently reproducible.

**Signal to a commercial audience.** Signals that a commercial offering exists
or is intended, and that the reference implementation is a demonstration rather
than a gift. That is a legitimate and honest signal. It is also a friction
signal: enterprise engineers routinely cannot get non-OSI licences approved for
even experimental internal use, which reduces the population of people who can
try the ideas. Weigh that against how much of the commercial value actually sits
in the mechanisms published here versus in the excluded platform, integrations,
data, and deployment architecture (see `docs/repository-scope.md`).

---

## Option 4: Remaining unlicensed

**What it permits.** Nothing. All rights reserved by default. Others may read
the repository; they have no permission to use, copy, modify, or redistribute
it. This is not a neutral or "decide later" state from a user's perspective — it
is the most restrictive of the four options, and it is the current state.

**Academic citation and reuse.** A reader can cite the paper and the repository,
and can point at the code as evidence that the mechanisms are implementable.
They cannot legally run modified copies, fork it, or include any of it in
supplementary material for their own work. Reproducibility claims sit awkwardly
here: the repository is technically reproducible — it runs offline with no
credentials — but not *legally* reusable, and reviewers increasingly notice the
difference.

**Contributions from others.** Effectively closed. There is no inbound licence
for a contributor to grant under and no outbound licence for them to receive, so
a careful contributor will not open a pull request. `CONTRIBUTING.md` currently
handles this by stating the deferral explicitly and asking contributors who are
not comfortable with it to wait.

**Patent position.** No grant is made and none is received, in either direction.

**Dependency compatibility.** Using MIT-licensed dependencies is fine; their
licences permit use in a proprietary work. The obligation to retain their
notices in any distribution still applies.

**Signal to a commercial audience.** Ambiguous, and ambiguity is the problem. It
can read as caution, as a decision not yet made, or as a demonstration that is
not really meant to be used. It also blocks concrete steps: package
distribution, some archive deposits and therefore a DOI, and inclusion in any
environment with an automated licence policy. As a deliberate, documented,
temporary state before publication it is defensible — which is exactly the state
the release gate records. As the permanent state of a published research
artifact it should be chosen knowingly, not by default.

---

## Comparison at a glance

| | Apache-2.0 | MIT | Research / non-commercial | Unlicensed |
|---|---|---|---|---|
| Commercial reuse permitted | Yes | Yes | No | No |
| OSI-approved | Yes | Yes | Generally no | N/A |
| Express patent grant | Yes | No | Varies, often none | No |
| Patent retaliation clause | Yes | No | Varies | N/A |
| Inbound contribution terms stated in licence | Yes (§5) | No | Varies | None |
| Likely to attract outside contributions | High | High | Low | Very low |
| Clears corporate legal review routinely | Yes | Yes | Often no | No |
| Compatible with MIT dependencies | Yes | Yes | Yes | Yes |
| Supports archival DOI where an open licence is required | Yes | Yes | Sometimes | No |

## Questions to answer before choosing

The comparison above does not resolve the decision. These do.

1. **Do you want commercial reuse of the reference implementation?** If a
   company should be able to lift these mechanisms into their own platform,
   Apache-2.0 or MIT. If not, the research-licence family, accepting its costs.
   Test the answer against `docs/repository-scope.md`: what is published here is
   the architecture around verification, not the excluded platform,
   integrations, prompts, data, or deployment.
2. **Do you want contributions from others?** Defect reports against a
   contract-governed implementation are the highest-value contribution this
   repository can receive, and the licence materially changes how many arrive.
   An OSI-approved licence gets them; a non-commercial one largely does not.
3. **Do you need patent protection?** If any patent position is connected to
   this work, or if you want contributors' patents licensed to users, Apache-2.0
   is the only option here that addresses it explicitly.
4. **Does the paper's venue require a specific licence?** Some venues, and some
   funders, require artifacts to be released under an open licence, or under a
   specific one, as a condition of publication or of an artifact-evaluation
   badge. Check before choosing, because this constraint overrides preference.
5. **Does this repository need to be citable and archivable?** The release
   process depends on obtaining `{{ARCHIVE_DOI}}` from an archive service, and
   some archives require an open licence to accept a deposit. If a DOI is
   required, that narrows the options.
6. **What is the intended relationship between this artifact and any future
   commercial work?** A licence is a durable signal about that relationship, and
   changing it later is possible for future versions but does not retract rights
   already granted under a published one.
7. **Is the current unlicensed state a decision or a deferral?** If it is a
   deferral, it must be resolved before publication. If it is a decision, it
   should be stated as one, with its consequences for reuse and citation
   acknowledged.

---

The licensing decision is the repository owner's to make. This document sets out
the options and their consequences; it does not make the choice.
