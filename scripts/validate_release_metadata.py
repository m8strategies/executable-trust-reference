#!/usr/bin/env python3
"""Block release while publication metadata is unresolved.

    python scripts/validate_release_metadata.py [--require-doi]

Ordinary CI passes with placeholders present — that is the working state of the
repository before publication. This script is the gate that must fail while they
remain, so an incomplete artifact cannot be tagged, archived, or cited.

Checks:

1. No unresolved ``{{PLACEHOLDER}}`` remains in a tracked file.
2. ``CITATION.cff`` exists, parses, and carries the required fields.
3. Paper references point at repository paths that actually exist.
4. The committed baseline reports are current.
5. A license decision has been recorded (a file exists, or the deferral is
   still explicitly documented).
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

PLACEHOLDER_RE = re.compile(r"\{\{([A-Z_]+)\}\}")

#: Placeholders that must be resolved before release. ARCHIVE_DOI is gated
#: separately: a DOI is minted by an archive service *after* a release exists,
#: so requiring it unconditionally would make the first release impossible.
REQUIRED_PLACEHOLDERS = ("REPOSITORY_URL", "RELEASE_TAG", "CANONICAL_PAPER_URL")

TEXT_SUFFIXES = frozenset({".py", ".md", ".yaml", ".yml", ".json", ".jsonl", ".toml", ".cff"})
EXCLUDED_PREFIXES = (".private/", ".venv/", ".git/")
SELF_PATH = "scripts/validate_release_metadata.py"

REQUIRED_CITATION_FIELDS = (
    "cff-version",
    "title",
    "authors",
    "message",
    "repository-code",
    "version",
)


def tracked_files() -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=REPO_ROOT,
            capture_output=True,
            check=True,
            text=True,
        )
        names = [n for n in out.stdout.split("\0") if n]
        if names:
            return [REPO_ROOT / n for n in names]
    except (subprocess.CalledProcessError, FileNotFoundError):
        pass
    return [
        p
        for p in REPO_ROOT.rglob("*")
        if p.is_file() and not any(part in {".git", ".venv", ".private"} for part in p.parts)
    ]


def find_placeholders(require_doi: bool) -> list[str]:
    """Return every unresolved placeholder occurrence that blocks release."""
    wanted = set(REQUIRED_PLACEHOLDERS)
    if require_doi:
        wanted.add("ARCHIVE_DOI")

    findings: list[str] = []
    for path in tracked_files():
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue
        if rel == SELF_PATH or any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            for name in PLACEHOLDER_RE.findall(line):
                if name in wanted:
                    findings.append(f"{rel}:{line_no}: unresolved {{{{{name}}}}}")
    return sorted(set(findings))


def check_citation() -> list[str]:
    """Verify CITATION.cff exists, parses, and carries the required fields."""
    path = REPO_ROOT / "CITATION.cff"
    if not path.is_file():
        return ["CITATION.cff is missing"]
    try:
        import yaml

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return [f"CITATION.cff does not parse: {exc}"]
    if not isinstance(data, dict):
        return ["CITATION.cff must contain a mapping"]

    problems = [
        f"CITATION.cff is missing required field {f!r}"
        for f in REQUIRED_CITATION_FIELDS
        if f not in data
    ]
    authors = data.get("authors")
    if not isinstance(authors, list) or not authors:
        problems.append("CITATION.cff declares no authors")
    return problems


def check_paper_references() -> list[str]:
    """Verify repository paths named by the paper exist.

    The paper lives beside the repository, one directory up. If it is not
    present this check is skipped rather than failed: the repository must
    remain independently valid.
    """
    paper = REPO_ROOT.parent.parent / "executable-trust.md"
    if not paper.is_file():
        return []

    text = paper.read_text(encoding="utf-8")
    problems: list[str] = []
    # Repository-relative paths the paper cites, in backticks.
    for match in re.findall(
        r"`((?:src|docs|contracts|schemas|evaluation|tests|scripts|reports)/[^`\s]+)`", text
    ):
        candidate = REPO_ROOT / match
        if not candidate.exists():
            problems.append(f"paper references missing repository path: {match}")
    return sorted(set(problems))


def check_baseline_current() -> list[str]:
    """Verify the committed baseline reports match a fresh run."""
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "evaluation" / "run_baseline.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ["committed baseline reports are stale; run: make baseline"]
    return []


def check_license_decision() -> list[str]:
    """A release must have made a licence decision, even if that decision is to defer."""
    options = REPO_ROOT / "docs" / "license-options.md"
    has_license = any((REPO_ROOT / n).is_file() for n in ("LICENSE", "LICENSE.md", "LICENSE.txt"))
    if has_license:
        return []
    if options.is_file():
        return [
            "no LICENSE file is present. The repository is unlicensed (all rights "
            "reserved by default). This is a deliberate deferral — see "
            "docs/license-options.md — and must be resolved by the owner before "
            "public release."
        ]
    return ["no LICENSE file and no docs/license-options.md: the licence decision is undocumented"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-doi",
        action="store_true",
        help="also require ARCHIVE_DOI to be resolved (use after archiving a release)",
    )
    args = parser.parse_args(argv)

    problems: list[str] = []
    problems += find_placeholders(args.require_doi)
    problems += check_citation()
    problems += check_paper_references()
    problems += check_baseline_current()
    problems += check_license_decision()

    if problems:
        print("RELEASE VALIDATION FAILED", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        print(
            f"\n{len(problems)} item(s) block release. Ordinary CI is expected to pass "
            "while these remain; this gate is what prevents publishing anyway.",
            file=sys.stderr,
        )
        return 1

    print("release metadata is complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
