#!/usr/bin/env python3
"""Validate every contract artifact and their cross-references.

    python scripts/validate_contracts.py

Schema validation proves each artifact is well formed on its own. This script
additionally proves the artifacts agree with each other and with the code:
reason codes trace to rules, rules reference only controlled codes, the
lifecycle is coherent, the outcome/strategy relation is declared correctly, and
every amendment preserves the version it amends.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from executable_trust.amendments import (  # noqa: E402
    assert_prior_versions_preserved,
    load_amendments,
)
from executable_trust.contracts import build_default_registry, validate_registry  # noqa: E402


def main() -> int:
    try:
        registry = build_default_registry()
    except Exception as exc:
        print(f"contract artifacts failed to load: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    report = validate_registry(registry)

    try:
        amendments = load_amendments()
        assert_prior_versions_preserved(amendments)
    except Exception as exc:
        print(f"amendment validation failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    if not report.ok:
        print("CONTRACT VALIDATION FAILED", file=sys.stderr)
        for err in report.errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    versions = registry.versions("executable-trust-reference")
    rule_ids = set()
    for cid, ver in registry.registered():
        rule_ids |= registry.get(cid, ver).all_rule_ids()

    print(
        f"contracts valid: {len(versions)} version(s) {versions}, "
        f"{len(rule_ids)} rule id(s), {len(registry.reason_codes)} reason code(s), "
        f"{len(amendments)} amendment(s), {report.checks_run} cross-checks"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
