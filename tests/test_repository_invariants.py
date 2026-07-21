"""Repository-level invariants.

These tests are about the *artifact*, not the code: traceability, the
publication boundary, reproducibility, release gating, and the claim that
nothing here needs a credential. They are the mechanism behind several
statements the README makes, so that those statements are checkable rather than
merely asserted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from executable_trust.authorization import DeterministicAuthorizer
from executable_trust.contracts import build_default_registry
from executable_trust.evaluation import evaluate, load_cases, to_json, to_markdown
from executable_trust.traceability import require_traceability, validate_traceability

# ---------------------------------------------------------------------------
# Traceability
# ---------------------------------------------------------------------------


def test_every_contract_rule_maps_to_a_test(repo_root):
    """Every executable rule has at least one test naming its identifier.

    This is what turns "every rule is tested" from a claim written once into a
    property that survives.
    """
    registry = build_default_registry()
    result = require_traceability(registry, repo_root / "tests")

    assert result.coverage_ratio == 1.0
    assert not result.untested
    assert not result.dangling


def test_no_test_pins_a_rule_that_no_longer_exists(repo_root):
    """A test naming a deleted rule passes forever without asserting anything."""
    result = validate_traceability(build_default_registry(), repo_root / "tests")

    assert not result.dangling, sorted(result.dangling)


def test_traceability_document_lists_every_rule(repo_root):
    """docs/paper-to-code-traceability.md must not fall behind the contract."""
    doc = repo_root / "docs" / "paper-to-code-traceability.md"
    text = doc.read_text(encoding="utf-8")

    registry = build_default_registry()
    rule_ids = set()
    for cid, ver in registry.registered():
        rule_ids |= registry.get(cid, ver).all_rule_ids()

    missing = sorted(rid for rid in rule_ids if rid not in text)
    assert not missing, f"traceability matrix omits: {missing}"


# ---------------------------------------------------------------------------
# Publication boundary
# ---------------------------------------------------------------------------


def test_publication_boundary_holds(repo_root):
    """No tracked public file contains a prohibited private identifier."""
    result = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "validate_publication_boundary.py")],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_boundary_scanner_detects_a_planted_identifier(repo_root, tmp_path, monkeypatch):
    """The scanner actually detects something, rather than passing vacuously.

    A validator nobody has seen fail is a validator nobody should trust.
    """
    sys.path.insert(0, str(repo_root / "scripts"))
    import validate_publication_boundary as boundary

    planted = tmp_path / "leak.md"
    # Assembled at runtime so this test file does not itself contain the term.
    planted.write_text("Motion" + "IQ is the product name.\n", encoding="utf-8")

    monkeypatch.setattr(boundary, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(boundary, "tracked_files", lambda: [planted])

    violations = boundary.scan()

    assert violations
    assert "prohibited identifier" in violations[0]


def test_boundary_scanner_matches_across_separators(repo_root, tmp_path, monkeypatch):
    """A term cannot be smuggled past by inserting a space, hyphen, or underscore."""
    sys.path.insert(0, str(repo_root / "scripts"))
    import validate_publication_boundary as boundary

    planted = tmp_path / "leak.md"
    planted.write_text("motion" + "-iq and motion" + "_iq and Motion" + " IQ\n", encoding="utf-8")

    monkeypatch.setattr(boundary, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(boundary, "tracked_files", lambda: [planted])

    assert len(boundary.scan()) >= 1


def test_private_directory_is_gitignored(repo_root):
    """The private extraction record must never enter the tracked tree."""
    gitignore = (repo_root / ".gitignore").read_text(encoding="utf-8")

    assert ".private/" in gitignore


def test_private_directory_is_not_tracked(repo_root):
    """Belt and braces: git itself must not be tracking anything under .private/."""
    result = subprocess.run(
        ["git", "ls-files", ".private"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == ""


# ---------------------------------------------------------------------------
# No credentials required
# ---------------------------------------------------------------------------


def test_no_external_service_credentials_are_referenced(repo_root):
    """The package requires no API key, cloud credential, or database URL.

    Scans the shipped package for the environment variables a system reaching
    an external model provider would need.
    """
    forbidden = (
        "ANTHROPIC_API_KEY",
        "OPENAI_API_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "DATABASE_URL",
    )
    offenders: list[str] = []

    for path in (repo_root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {name}" for name in forbidden if name in text]

    assert not offenders, offenders


def test_package_imports_no_network_library(repo_root):
    """No HTTP, socket, or model-provider client is imported by the package."""
    forbidden = ("import requests", "import httpx", "import socket", "import anthropic")
    offenders: list[str] = []

    for path in (repo_root / "src").rglob("*.py"):
        text = path.read_text(encoding="utf-8")
        offenders += [f"{path.name}: {tok}" for tok in forbidden if tok in text]

    assert not offenders, offenders


# ---------------------------------------------------------------------------
# Reproducibility
# ---------------------------------------------------------------------------


def test_baseline_is_byte_reproducible(repo_root):
    """Two runs of the suite produce identical reports.

    Reproducibility is claimed by this repository, so it is tested rather than
    hoped for. Any timestamp, random identifier, or wall-clock duration leaking
    into a report breaks this.
    """
    registry = build_default_registry()
    contract = registry.resolve("executable-trust-reference", "1.0")
    cases = load_cases(repo_root / "evaluation" / "golden_set.jsonl")

    first = evaluate(cases, registry, contract, authorizer=DeterministicAuthorizer())
    second = evaluate(cases, registry, contract, authorizer=DeterministicAuthorizer())

    assert to_json(first) == to_json(second)
    assert to_markdown(first) == to_markdown(second)


def test_committed_baseline_matches_a_fresh_run(repo_root):
    """The committed reports are current.

    A stale committed baseline is worse than none: it is a number people trust
    that no longer describes the code.
    """
    result = subprocess.run(
        [sys.executable, str(repo_root / "evaluation" / "run_baseline.py"), "--check"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_baseline_gate_passes(repo_root):
    """ET-EVAL-001: every golden case matches its human-authored expectation."""
    registry = build_default_registry()
    contract = registry.resolve("executable-trust-reference", "1.0")
    cases = load_cases(repo_root / "evaluation" / "golden_set.jsonl")

    run = evaluate(cases, registry, contract, authorizer=DeterministicAuthorizer())

    assert run.summary.gate_passed, [f.divergence for f in run.failures]
    assert run.summary.total == len(cases)


def test_baseline_reports_are_labelled_synthetic(repo_root):
    """ET-EVAL-002: the reports state their own scope, in both formats."""
    md = (repo_root / "reports" / "reference-baseline.md").read_text(encoding="utf-8")
    payload = json.loads((repo_root / "reports" / "reference-baseline.json").read_text("utf-8"))

    assert "Reference implementation synthetic baseline" in md
    assert payload["label"] == "Reference implementation synthetic baseline"
    assert "not a measurement of any production system" in payload["boundary_note"]


def test_reports_contain_no_timestamp(repo_root):
    """A report that differs on every run cannot be diffed."""
    payload = json.loads((repo_root / "reports" / "reference-baseline.json").read_text("utf-8"))

    assert "timestamp" not in payload["provenance"]
    assert "generated_at" not in payload["provenance"]


# ---------------------------------------------------------------------------
# Release gating
# ---------------------------------------------------------------------------


def _run_release_validation(repo_root, *args):
    return subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "validate_release_metadata.py"), *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )


def test_release_validation_passes_before_the_doi_exists(repo_root):
    """Pre-DOI release preparation is intentionally allowed.

    A DOI is minted by the archive service *after* a release exists, so
    requiring one unconditionally would make the first release impossible.
    Every other publication field must already be resolved for this to pass.
    """
    result = _run_release_validation(repo_root)

    assert result.returncode == 0, result.stderr
    assert "release metadata is complete" in result.stdout


def test_release_validation_blocks_on_an_unresolved_doi(repo_root):
    """--require-doi is the gate for the post-archive step.

    Run after Zenodo ingests the release. Until the DOI is written back into
    the metadata and the paper, this must refuse.
    """
    result = _run_release_validation(repo_root, "--require-doi")

    assert result.returncode == 1
    assert "RELEASE VALIDATION FAILED" in result.stderr
    assert "{{ARCHIVE_DOI}}" in result.stderr


def test_canonical_paper_url_is_resolved(repo_root):
    """The paper is published, so no canonical-URL placeholder may remain.

    Scans tracked files rather than a fixed list, so a new file reintroducing
    the placeholder is caught.
    """
    result = subprocess.run(["git", "ls-files"], cwd=repo_root, capture_output=True, text=True)
    offenders = []
    for name in result.stdout.splitlines():
        path = repo_root / name
        if path.suffix.lower() not in {".md", ".yaml", ".yml", ".json", ".toml", ".cff", ".py"}:
            continue
        if not path.is_file():
            continue
        if "{{CANONICAL" + "_PAPER_URL}}" in path.read_text(encoding="utf-8"):
            offenders.append(name)

    assert not offenders, f"unresolved canonical paper URL in: {offenders}"


def test_canonical_paper_url_is_the_publication_venue(repo_root):
    """The paper's canonical location is the publication page, not this repository.

    Guards against the repository drifting into describing itself as where the
    paper lives. They are different artifacts with different roles.
    """
    readme = (repo_root / "README.md").read_text(encoding="utf-8")

    assert "https://www.m8strategies.com/blog/executable-trust" in readme
    assert "not** the canonical" in readme or "not the canonical" in readme


def test_citation_metadata_is_present_and_parses(repo_root):
    """CITATION.cff must exist and carry the fields a citation needs."""
    import yaml

    data = yaml.safe_load((repo_root / "CITATION.cff").read_text(encoding="utf-8"))

    assert data["title"]
    assert data["authors"]
    assert data["authors"][0]["family-names"] == "Mahmoud"


def test_paper_references_resolve_to_real_paths(repo_root):
    """Every repository path the paper cites must exist.

    Skipped when the paper is not present beside the repository, so the
    repository remains independently valid.
    """
    import re

    paper = repo_root.parent.parent / "executable-trust.md"
    if not paper.is_file():
        pytest.skip("paper not present beside the repository")

    text = paper.read_text(encoding="utf-8")
    pattern = r"`((?:src|docs|contracts|schemas|evaluation|tests|scripts|reports)/[^`\s]+)`"
    missing = [m for m in set(re.findall(pattern, text)) if not (repo_root / m).exists()]

    assert not missing, f"paper cites missing paths: {sorted(missing)}"


def test_scripts_are_executable_as_modules(repo_root):
    """Every validation script runs and returns a defined exit code."""
    for name, expected in (
        ("validate_contracts.py", 0),
        ("validate_traceability.py", 0),
        ("validate_publication_boundary.py", 0),
    ):
        result = subprocess.run(
            [sys.executable, str(repo_root / "scripts" / name)],
            cwd=repo_root,
            capture_output=True,
            text=True,
        )
        assert result.returncode == expected, f"{name}: {result.stderr}"


def test_golden_set_and_reports_agree_on_case_count(repo_root):
    """The committed report describes the golden set that is on disk."""
    cases = load_cases(repo_root / "evaluation" / "golden_set.jsonl")
    payload = json.loads((repo_root / "reports" / "reference-baseline.json").read_text("utf-8"))

    assert payload["provenance"]["case_count"] == len(cases)
    assert len(payload["cases"]) == len(cases)


def test_repository_has_no_pycache_tracked(repo_root):
    """Build artifacts must not enter the tracked tree."""
    result = subprocess.run(["git", "ls-files"], cwd=repo_root, capture_output=True, text=True)
    tracked = [Path(p) for p in result.stdout.splitlines() if p]

    assert not [p for p in tracked if "__pycache__" in p.parts]


# ---------------------------------------------------------------------------
# Research metadata: CITATION.cff and .zenodo.json must not drift apart
# ---------------------------------------------------------------------------


def test_citation_and_zenodo_metadata_agree(repo_root):
    """Both files describe the same artifact and must stay consistent.

    GitHub surfaces citation guidance from CITATION.cff; Zenodo prefers
    .zenodo.json when both are present. Two files describing one artifact is
    exactly the shape that drifts, so the agreement is asserted rather than
    assumed.
    """
    import yaml

    cff = yaml.safe_load((repo_root / "CITATION.cff").read_text(encoding="utf-8"))
    zen = json.loads((repo_root / ".zenodo.json").read_text(encoding="utf-8"))

    assert cff["title"] == zen["title"]
    assert cff["version"] == zen["version"]
    assert cff["license"] == zen["license"]

    cff_author = cff["authors"][0]
    assert (
        zen["creators"][0]["name"] == f"{cff_author['family-names']}, {cff_author['given-names']}"
    )
    assert zen["creators"][0]["affiliation"] == cff_author["affiliation"]
    assert set(cff["keywords"]) == set(zen["keywords"])


def test_zenodo_declares_the_repository_and_paper_relationship(repo_root):
    """The artifact must point at both the repository and the paper it supplements."""
    zen = json.loads((repo_root / ".zenodo.json").read_text(encoding="utf-8"))
    relations = {r["relation"]: r["identifier"] for r in zen["related_identifiers"]}

    assert "isSupplementTo" in relations
    assert "github.com/m8strategies/executable-trust-reference" in relations["isSupplementedBy"]


def test_zenodo_does_not_self_declare_a_doi(repo_root):
    """Zenodo mints the DOI on ingest; declaring one here would be a fabrication."""
    zen = json.loads((repo_root / ".zenodo.json").read_text(encoding="utf-8"))

    assert "doi" not in zen


def test_license_is_apache_2_0(repo_root):
    """The licence decision is recorded in every place that asserts one."""
    import tomllib

    license_text = (repo_root / "LICENSE").read_text(encoding="utf-8")
    assert "Apache License" in license_text
    assert "Version 2.0, January 2004" in license_text
    assert "[name of copyright owner]" not in license_text

    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text(encoding="utf-8"))
    assert pyproject["project"]["license"] == "Apache-2.0"


def test_baseline_runner_accepts_an_out_of_tree_output_directory(repo_root, tmp_path):
    """`--out` may point outside the repository, as it does in CI.

    Regression: the runner rendered its "wrote <path>" lines with
    `Path.relative_to(REPO_ROOT)` unconditionally, which raises when the output
    directory is not inside the working tree. The reports were written
    correctly and the gate passed; the run still failed. Caught by CI, which
    writes to a scratch directory, and never by a local run using the default.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "evaluation" / "run_baseline.py"),
            "--out",
            str(tmp_path / "out"),
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert "gate PASS" in result.stdout
    assert (tmp_path / "out" / "reference-baseline.md").is_file()
    assert (tmp_path / "out" / "reference-baseline.json").is_file()
