"""Command-line entry point.

    executable-trust contracts     validate every contract artifact
    executable-trust baseline      run the synthetic reference baseline
    executable-trust traceability  check every rule maps to a test
    executable-trust rules         list contract rules and their reason codes

A thin surface over the library. Everything it does is available
programmatically, and no behaviour lives only here.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from executable_trust import __version__

REPO_ROOT = Path(__file__).resolve().parents[2]


def _cmd_contracts(_: argparse.Namespace) -> int:
    from executable_trust.amendments import assert_prior_versions_preserved, load_amendments
    from executable_trust.contracts import build_default_registry, validate_registry

    registry = build_default_registry()
    report = validate_registry(registry)
    amendments = load_amendments()
    assert_prior_versions_preserved(amendments)

    if not report.ok:
        for err in report.errors:
            print(f"  {err}", file=sys.stderr)
        return 1

    print(
        f"contracts valid: versions {registry.versions('executable-trust-reference')}, "
        f"{len(registry.reason_codes)} reason codes, {len(amendments)} amendment(s), "
        f"{report.checks_run} cross-checks"
    )
    return 0


def _cmd_baseline(args: argparse.Namespace) -> int:
    sys.path.insert(0, str(REPO_ROOT / "evaluation"))
    from run_baseline import main as run_baseline  # type: ignore[import-not-found]

    result: int = run_baseline(["--check"] if args.check else [])
    return result


def _cmd_traceability(_: argparse.Namespace) -> int:
    from executable_trust.contracts import build_default_registry
    from executable_trust.traceability import validate_traceability

    result = validate_traceability(build_default_registry(), REPO_ROOT / "tests")
    for rule_id in sorted(result.untested):
        print(f"  untested rule: {rule_id}", file=sys.stderr)
    for rule_id in sorted(result.dangling):
        print(f"  dangling test reference: {rule_id}", file=sys.stderr)
    if not result.ok:
        return 1
    print(f"traceability holds: {len(result.rule_ids)} rule(s) fully covered")
    return 0


def _cmd_rules(args: argparse.Namespace) -> int:
    from executable_trust.contracts import build_default_registry

    registry = build_default_registry()
    contract = registry.get("executable-trust-reference", args.contract_version)

    print(f"{contract.contract_id} v{contract.version} ({contract.ratification.status.value})")
    print(f"{'RULE ID':<14} {'NAME':<44} REASON CODE")
    print("-" * 92)
    for rule_id in sorted(contract.all_rule_ids()):
        rule = contract.rule(rule_id)
        name = rule.rule if rule else "(structured section)"
        code = (rule.reason_code if rule else None) or "-"
        print(f"{rule_id:<14} {name:<44} {code}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="executable-trust",
        description="Executable Trust reference implementation",
    )
    parser.add_argument("--version", action="version", version=f"executable-trust {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("contracts", help="validate contract artifacts").set_defaults(
        func=_cmd_contracts
    )

    baseline = sub.add_parser("baseline", help="run the synthetic reference baseline")
    baseline.add_argument("--check", action="store_true", help="verify committed reports")
    baseline.set_defaults(func=_cmd_baseline)

    sub.add_parser("traceability", help="check rule-to-test coverage").set_defaults(
        func=_cmd_traceability
    )

    rules = sub.add_parser("rules", help="list contract rules")
    rules.add_argument("--contract-version", default="1.0")
    rules.set_defaults(func=_cmd_rules)

    args = parser.parse_args(argv)
    result: int = args.func(args)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
