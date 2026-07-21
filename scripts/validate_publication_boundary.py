#!/usr/bin/env python3
"""Scan tracked files for prohibited private identifiers.

    python scripts/validate_publication_boundary.py [--extra-terms FILE]

This repository is a public artifact derived from work that also produced a
private commercial system. The boundary between them is maintained by review,
and review is fallible, so it is also maintained by this scanner — which runs
in CI and fails the build.

**Two term lists, deliberately.** The list below is safe to publish: it names
only what is already public knowledge or is generic enough to leak nothing. A
richer list of private service names, hostnames, table names, and API prefixes
belongs in a local file that is gitignored, because a public scanner containing
every private identifier would itself be the disclosure it exists to prevent.

Only **tracked** files are scanned. `.private/` is excluded by design: it is
gitignored, never published, and is the one place private identifiers are
permitted to appear.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

#: Publication-safe prohibited terms. Matched case-insensitively, with flexible
#: separators so a term cannot be smuggled past by inserting a space, hyphen, or
#: underscore.
PROHIBITED_TERMS: tuple[str, ...] = (
    "motioniq",
    "motion iq",
    "m8 agent",
    "m8_agent",
)

#: Patterns for material that must never appear regardless of naming.
PROHIBITED_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bsk-[A-Za-z0-9]{16,}\b", "possible API key"),
    (r"\bAKIA[0-9A-Z]{16}\b", "AWS access key id"),
    (r"-----BEGIN [A-Z ]*PRIVATE KEY-----", "private key block"),
    (r"\bpostgres(?:ql)?://[^\s\"'<>]*:[^\s\"'@<>]+@", "database URL with credentials"),
    (r"\bANTHROPIC_API_KEY\s*=\s*['\"]?[A-Za-z0-9_\-]{8,}", "populated API key variable"),
)

#: Extensions that are scanned. Binary formats are skipped rather than decoded.
TEXT_SUFFIXES = frozenset(
    {
        ".py",
        ".md",
        ".yaml",
        ".yml",
        ".json",
        ".jsonl",
        ".toml",
        ".cfg",
        ".ini",
        ".txt",
        ".sh",
        ".cff",
        ".editorconfig",
        ".gitignore",
        "",
    }
)

#: Paths never treated as public artifacts.
EXCLUDED_PREFIXES = (".private/", ".venv/", ".git/")

#: This file necessarily contains the prohibited terms in order to search for
#: them. Excluding it by name is honest; excluding it by a clever encoding
#: would hide the term list from a reviewer, which defeats the purpose.
SELF_PATH = "scripts/validate_publication_boundary.py"


def _flexible(term: str) -> re.Pattern[str]:
    """Compile a term to a pattern.

    Two matching modes, because product names and code identifiers need
    different treatment:

    **Flexible (default).** ``motion iq`` also matches ``motioniq``,
    ``motion-iq``, and ``motion_iq``. Correct for a product name, which a
    careless author may write any of those ways.

    **Exact (prefix the term with ``=``).** ``=JUDGE_MODEL`` matches only that
    literal token, word-bounded. Correct for code identifiers: flexing
    separators on ``JUDGE_MODEL`` would also match the ordinary English phrase
    "judge model", and a scanner that cries wolf is a scanner people learn to
    ignore.
    """
    term = term.strip()
    if term.startswith("="):
        return re.compile(
            r"(?<![A-Za-z0-9_])" + re.escape(term[1:]) + r"(?![A-Za-z0-9_])", re.IGNORECASE
        )
    parts = [re.escape(p) for p in re.split(r"[\s_-]+", term) if p]
    return re.compile(r"[\s_\-]*".join(parts), re.IGNORECASE)


def tracked_files() -> list[Path]:
    """Return git-tracked files, falling back to a filesystem walk.

    Tracked files are the right universe: an untracked scratch file is not a
    published artifact, and scanning it would produce failures nobody can act
    on.
    """
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


def load_extra_terms(path: Path | None) -> tuple[str, ...]:
    """Load additional prohibited terms from a local, gitignored file."""
    if path is None:
        default = REPO_ROOT / ".boundary-terms.local.txt"
        path = default if default.is_file() else None
    if path is None or not path.is_file():
        return ()
    return tuple(
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    )


def scan(extra_terms: tuple[str, ...] = ()) -> list[str]:
    """Return a list of violations. Empty means the boundary holds."""
    violations: list[str] = []
    term_patterns = [(t, _flexible(t)) for t in (*PROHIBITED_TERMS, *extra_terms)]
    compiled_patterns = [(re.compile(p), label) for p, label in PROHIBITED_PATTERNS]

    for path in tracked_files():
        try:
            rel = path.relative_to(REPO_ROOT).as_posix()
        except ValueError:
            continue

        if rel == SELF_PATH or any(rel.startswith(p) for p in EXCLUDED_PREFIXES):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if not path.is_file():
            continue

        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            for term, pattern in term_patterns:
                if pattern.search(line):
                    violations.append(
                        f"{rel}:{line_no}: prohibited identifier {term.lstrip(chr(61))!r}"
                    )
            for pattern, label in compiled_patterns:
                if pattern.search(line):
                    violations.append(f"{rel}:{line_no}: {label}")

    return sorted(set(violations))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--extra-terms",
        type=Path,
        default=None,
        help="local gitignored file of additional prohibited terms, one per line",
    )
    args = parser.parse_args(argv)

    extra = load_extra_terms(args.extra_terms)
    violations = scan(extra)

    if violations:
        print("PUBLICATION BOUNDARY VIOLATION", file=sys.stderr)
        for v in violations:
            print(f"  {v}", file=sys.stderr)
        print(
            f"\n{len(violations)} violation(s). These identifiers must not appear in "
            "a tracked public file.",
            file=sys.stderr,
        )
        return 1

    scanned = len(PROHIBITED_TERMS) + len(extra)
    extra_note = f" (+{len(extra)} local)" if extra else " (no local term file loaded)"
    print(f"publication boundary holds: {scanned} term(s) checked{extra_note}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
