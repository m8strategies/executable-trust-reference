"""Deterministic Markdown and JSON reports.

Reports are byte-identical across runs. No timestamps, no durations, no git
revision, no random identifiers — anything that varies without the system
having changed is excluded, because a report that differs on every run cannot
be diffed, and a baseline you cannot diff is not a baseline.

Every report is labelled *Reference implementation synthetic baseline*, and the
label is not decoration. It is the boundary between what this repository
measured and what the accompanying paper reports from production.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from executable_trust.evaluation.models import CaseResult, SuiteSummary
from executable_trust.evaluation.runner import SuiteRun

BASELINE_LABEL = "Reference implementation synthetic baseline"

_BOUNDARY_NOTE = (
    "These results describe this reference implementation's conformance to its own "
    "human-authored synthetic golden set, using a deterministic verifier and a "
    "fictional evidence corpus. They are not a measurement of any production "
    "system, they do not reproduce production performance, and they must not be "
    "compared numerically with the field observations reported in the paper."
)


def to_json(run: SuiteRun) -> dict[str, Any]:
    """Serialise a run to a plain, sorted, deterministic structure."""
    return {
        "label": BASELINE_LABEL,
        "provenance": run.provenance,
        "summary": run.summary.model_dump(mode="json"),
        "cases": [_case_json(r) for r in run.results],
        "boundary_note": _BOUNDARY_NOTE,
    }


def write_json(run: SuiteRun, path: Path | str) -> Path:
    """Write the JSON report with stable key ordering and a trailing newline."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(to_json(run), indent=2, sort_keys=True, ensure_ascii=False)
    path.write_text(payload + "\n", encoding="utf-8")
    return path


def to_markdown(run: SuiteRun) -> str:
    """Render a human-readable report."""
    s = run.summary
    p = run.provenance
    lines: list[str] = [
        f"# {BASELINE_LABEL}",
        "",
        "> **Scope.** " + _BOUNDARY_NOTE,
        "",
        "## Provenance",
        "",
        f"- **Package version:** `{p['package_version']}`",
        f"- **Contract:** `{p['contract_id']}` v`{p['contract_version']}` "
        f"({p['ratification_status']})",
        f"- **Cases:** {p['case_count']}",
        f"- **Verifier:** {p['verifier']}",
        f"- **Evidence:** {p['evidence']}",
        f"- **Population:** {p['population']}",
        "",
        "## Summary",
        "",
        f"- **Passed:** {s.passed}/{s.total} ({s.pass_rate:.1%})",
        f"- **Failed:** {s.failed}",
        f"- **Gate:** requires {s.gate_minimum_pass_rate:.0%} — "
        f"**{'PASS' if s.gate_passed else 'FAIL'}**",
        "",
        "## By category",
        "",
        "| Category | Passed | Total |",
        "|---|---:|---:|",
    ]
    for category, counts in s.by_category.items():
        lines.append(f"| `{category}` | {counts['passed']} | {counts['total']} |")

    lines += [
        "",
        "## Cases",
        "",
        "| Case | Expected | Actual | Reason code | Generated? | Pass |",
        "|---|---|---|---|:--:|:--:|",
    ]
    for r in run.results:
        expected = _describe(r.expected_outcome, r.expected_strategy, r.expected_reason_code)
        actual = _describe(r.actual_outcome, r.actual_strategy, r.actual_reason_code)
        generated = "yes" if r.generation_invoked else "no"
        lines.append(
            f"| `{r.case_id}` | {expected} | {actual} | "
            f"`{_value(r.actual_reason_code)}` | {generated} | "
            f"{'PASS' if r.passed else 'FAIL'} |"
        )

    failures = run.failures
    if failures:
        lines += ["", "## Divergences", ""]
        for r in failures:
            lines.append(f"- `{r.case_id}` — {r.divergence}")

    lines.append("")
    return "\n".join(lines)


def write_markdown(run: SuiteRun, path: Path | str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_markdown(run), encoding="utf-8")
    return path


def _case_json(r: CaseResult) -> dict[str, Any]:
    return {
        "case_id": r.case_id,
        "category": r.category,
        "passed": r.passed,
        "expected": {
            "outcome": r.expected_outcome.value,
            "strategy": _value(r.expected_strategy),
            "reason_code": _value(r.expected_reason_code),
        },
        "actual": {
            "outcome": r.actual_outcome.value,
            "strategy": _value(r.actual_strategy),
            "reason_code": _value(r.actual_reason_code),
        },
        "generation_invoked": r.generation_invoked,
        "divergence": r.divergence,
    }


def _describe(outcome: Any, strategy: Any, reason_code: Any) -> str:
    if strategy is not None:
        return f"{outcome.value}/{strategy.value}"
    if reason_code is not None:
        return f"{outcome.value}"
    return str(outcome.value)


def _value(v: Any) -> str | None:
    if v is None:
        return None
    result: str = getattr(v, "value", str(v))
    return result


def summary_line(summary: SuiteSummary) -> str:
    """One-line result, used by the CLI and CI logs."""
    verdict = "PASS" if summary.gate_passed else "FAIL"
    return (
        f"{BASELINE_LABEL}: {summary.passed}/{summary.total} "
        f"({summary.pass_rate:.1%}) — gate {verdict}"
    )
