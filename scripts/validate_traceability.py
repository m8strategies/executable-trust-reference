#!/usr/bin/env python3
"""Fail the build when a contract rule has no test naming it.

    python scripts/validate_traceability.py

Checks both directions: no untested rule, and no test pinning a rule that no
longer exists. The second matters as much as the first, because a test naming a
deleted rule passes forever without asserting anything.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from executable_trust.contracts import build_default_registry  # noqa: E402
from executable_trust.traceability import validate_traceability  # noqa: E402


def main() -> int:
    registry = build_default_registry()
    result = validate_traceability(registry, REPO_ROOT / "tests")

    if result.untested:
        print("TRACEABILITY FAILED — contract rules with no test naming them:", file=sys.stderr)
        for rule_id in sorted(result.untested):
            print(f"  {rule_id}", file=sys.stderr)
    if result.dangling:
        print("TRACEABILITY FAILED — tests name rules no contract declares:", file=sys.stderr)
        for rule_id in sorted(result.dangling):
            print(f"  {rule_id}", file=sys.stderr)

    if not result.ok:
        return 1

    print(f"traceability holds: {len(result.rule_ids)} rule id(s), 100% covered by tests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
