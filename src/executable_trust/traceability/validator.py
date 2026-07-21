"""Traceability: every contract rule maps to at least one test.

"Every rule is tested" is the kind of claim that is true when written and
quietly false three months later. This module turns it into a build failure.

The mechanism is deliberately crude: scan the test suite's source for rule
identifiers appearing as literals. Crude has a virtue here — it cannot be
satisfied by a test that merely *imports* something, only by one that names the
rule it pins. A test that names ``ET-VER-002`` is asserting it is about
``ET-VER-002``, and if the rule is deleted the reference dangles.

Two directions are checked, and the second matters as much as the first:

- every rule identifier appears in at least one test (no untested rule);
- every rule identifier referenced by a test exists in a contract (no test
  pinning a rule that was removed, silently passing forever).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from executable_trust.contracts.registry import ContractRegistry
from executable_trust.domain.errors import TraceabilityError

RULE_ID_PATTERN = re.compile(r"\bET-[A-Z]+-\d{3}\b")


@dataclass
class TraceabilityResult:
    """Outcome of a traceability scan."""

    rule_ids: set[str] = field(default_factory=set)
    referenced: set[str] = field(default_factory=set)
    coverage: dict[str, list[str]] = field(default_factory=dict)

    @property
    def untested(self) -> set[str]:
        """Rules declared in a contract that no test names."""
        return self.rule_ids - self.referenced

    @property
    def dangling(self) -> set[str]:
        """Rules named by a test that no contract declares."""
        return self.referenced - self.rule_ids

    @property
    def ok(self) -> bool:
        return not self.untested and not self.dangling

    @property
    def coverage_ratio(self) -> float:
        if not self.rule_ids:
            return 0.0
        return len(self.rule_ids & self.referenced) / len(self.rule_ids)


def collect_rule_ids(registry: ContractRegistry) -> set[str]:
    """Every rule identifier declared by any registered contract version."""
    ids: set[str] = set()
    for contract_id, version in registry.registered():
        ids |= registry.get(contract_id, version).all_rule_ids()
    return ids


def scan_tests(test_root: Path | str) -> dict[str, list[str]]:
    """Map each rule identifier to the test files naming it."""
    root = Path(test_root)
    coverage: dict[str, list[str]] = {}
    if not root.is_dir():
        return coverage

    for path in sorted(root.rglob("test_*.py")):
        text = path.read_text(encoding="utf-8")
        for rule_id in sorted(set(RULE_ID_PATTERN.findall(text))):
            coverage.setdefault(rule_id, []).append(str(path.relative_to(root)))
    return coverage


def validate_traceability(
    registry: ContractRegistry,
    test_root: Path | str,
) -> TraceabilityResult:
    """Scan and return the result without raising."""
    rule_ids = collect_rule_ids(registry)
    coverage = scan_tests(test_root)
    return TraceabilityResult(
        rule_ids=rule_ids,
        referenced=set(coverage),
        coverage=coverage,
    )


def require_traceability(registry: ContractRegistry, test_root: Path | str) -> TraceabilityResult:
    """Scan and raise on any gap in either direction."""
    result = validate_traceability(registry, test_root)
    if result.untested:
        raise TraceabilityError(
            "contract rules with no test naming them: "
            f"{sorted(result.untested)}. Every executable rule must map to at "
            "least one test; add a test that names the identifier."
        )
    if result.dangling:
        raise TraceabilityError(
            "tests name rule identifiers that no contract declares: "
            f"{sorted(result.dangling)}. A test pinning a removed rule passes "
            "forever without asserting anything."
        )
    return result
