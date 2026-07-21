#!/usr/bin/env python3
"""Run the synthetic reference baseline and write reports.

    python evaluation/run_baseline.py [--out reports/] [--check]

Exit codes:
    0  gate passed
    1  gate failed (a case diverged from its human-authored expectation)
    2  the suite could not run (missing golden set, invalid case, bad contract)

``--check`` regenerates the reports in memory and compares them to what is on
disk without writing, so CI can prove the committed baseline is current. A
stale committed baseline is worse than none: it is a number people trust that
no longer describes the code.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from executable_trust.authorization import DeterministicAuthorizer  # noqa: E402
from executable_trust.contracts import build_default_registry  # noqa: E402
from executable_trust.evaluation import (  # noqa: E402
    evaluate,
    load_cases,
    summary_line,
    to_markdown,
    write_json,
    write_markdown,
)
from executable_trust.evaluation.reporting import to_json  # noqa: E402

GOLDEN_SET = REPO_ROOT / "evaluation" / "golden_set.jsonl"
DEFAULT_OUT = REPO_ROOT / "reports"
CONTRACT_VERSION = "1.0"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--golden-set", type=Path, default=GOLDEN_SET)
    parser.add_argument(
        "--check",
        action="store_true",
        help="compare against committed reports instead of writing them",
    )
    args = parser.parse_args(argv)

    try:
        registry = build_default_registry()
        contract = registry.resolve("executable-trust-reference", CONTRACT_VERSION)
        cases = load_cases(args.golden_set)
    except Exception as exc:
        print(f"could not run the suite: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2

    run = evaluate(cases, registry, contract, authorizer=DeterministicAuthorizer())

    md_path = args.out / "reference-baseline.md"
    json_path = args.out / "reference-baseline.json"

    if args.check:
        drifted = _check(run, md_path, json_path)
        if drifted:
            print(
                "committed baseline reports are stale:\n  " + "\n  ".join(drifted),
                file=sys.stderr,
            )
            print("regenerate with: python evaluation/run_baseline.py", file=sys.stderr)
            return 1
        print("committed baseline reports are current")
    else:
        write_markdown(run, md_path)
        write_json(run, json_path)
        print(f"wrote {_display(md_path)}")
        print(f"wrote {_display(json_path)}")

    print(summary_line(run.summary))

    if not run.summary.gate_passed:
        for failure in run.failures:
            print(f"  FAIL {failure.case_id}: {failure.divergence}", file=sys.stderr)
        return 1
    return 0


def _display(path: Path) -> str:
    """Render a path relative to the repository when it is inside it.

    ``--out`` may legitimately point anywhere — CI writes to a scratch
    directory outside the working tree — so this must not assume containment.
    An earlier version called ``relative_to`` unconditionally and crashed on
    exactly that case, after the reports had already been written correctly.
    """
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _check(run, md_path: Path, json_path: Path) -> list[str]:
    """Return a list of drift descriptions; empty means the reports are current."""
    import json

    drift: list[str] = []
    expected_md = to_markdown(run)
    if not md_path.is_file():
        drift.append(f"{md_path.name} is missing")
    elif md_path.read_text(encoding="utf-8") != expected_md:
        drift.append(f"{md_path.name} differs from a fresh run")

    expected_json = to_json(run)
    if not json_path.is_file():
        drift.append(f"{json_path.name} is missing")
    else:
        on_disk = json.loads(json_path.read_text(encoding="utf-8"))
        if on_disk != expected_json:
            drift.append(f"{json_path.name} differs from a fresh run")
    return drift


if __name__ == "__main__":
    raise SystemExit(main())
