"""Contract artifacts: loading, resolution, vocabulary, and amendments."""

from __future__ import annotations

import pytest
import yaml

from executable_trust.amendments import (
    ContractAmendment,
    assert_prior_versions_preserved,
    contract_path_for,
    load_amendments,
)
from executable_trust.contracts import build_default_registry, load_contract, validate_registry
from executable_trust.contracts.registry import ContractRegistry
from executable_trust.domain.enums import RatificationStatus, ReasonCode
from executable_trust.domain.errors import (
    ContractNotFound,
    ContractNotRatified,
    ContractValidationError,
    UncontrolledReasonCode,
)

pytestmark = pytest.mark.contract

CONTRACT_ID = "executable-trust-reference"


# ---------------------------------------------------------------------------
# ET-CON-001 / ET-CON-002 — resolution fails closed
# ---------------------------------------------------------------------------


def test_unknown_contract_version_fails_closed(registry: ContractRegistry):
    """ET-CON-001: the binary never guesses which rules applied."""
    with pytest.raises(ContractNotFound):
        registry.resolve(CONTRACT_ID, "9.9")


def test_unknown_contract_id_fails_closed(registry: ContractRegistry):
    """ET-CON-001: an unregistered contract identifier is equally unresolvable."""
    with pytest.raises(ContractNotFound):
        registry.resolve("some-other-contract", "1.0")


def test_draft_contract_cannot_govern(registry: ContractRegistry):
    """ET-CON-002: a draft describes an intention; only a ratified one is a rule."""
    draft = registry.get(CONTRACT_ID, "0.9")
    assert draft.ratification.status is RatificationStatus.DRAFT
    assert draft.is_ratified is False

    with pytest.raises(ContractNotRatified, match="may not govern"):
        registry.resolve(CONTRACT_ID, "0.9")


def test_draft_contract_still_loads(registry: ContractRegistry):
    """ET-CON-002: loading in order to inspect is legitimate; governing is not.

    Separating "can be read" from "may govern" is what lets a draft be reviewed
    before it is ratified.
    """
    assert registry.get(CONTRACT_ID, "0.9") is not None


def test_ratified_contract_resolves(registry: ContractRegistry):
    """ET-CON-002: the ratified version governs."""
    contract = registry.resolve(CONTRACT_ID, "1.0")

    assert contract.is_ratified is True
    assert contract.version == "1.0"


# ---------------------------------------------------------------------------
# ET-CON-003 — malformed contracts fail validation
# ---------------------------------------------------------------------------


def test_malformed_contract_fails_validation(tmp_path, repo_root):
    """ET-CON-003: a contract that does not satisfy the schema cannot be loaded."""
    source = yaml.safe_load(
        (repo_root / "contracts" / "executable-trust-v1.0.yaml").read_text(encoding="utf-8")
    )
    del source["verification"]["rules"]
    broken = tmp_path / "broken.yaml"
    broken.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ContractValidationError, match="schema validation"):
        load_contract(broken)


def test_contract_declaring_fail_open_is_rejected(tmp_path, repo_root):
    """ET-CON-003: fail_closed is structurally constant.

    A contract asserting fail_closed:false is not an Executable Trust contract,
    and the schema refuses to load it rather than honouring it.
    """
    source = yaml.safe_load(
        (repo_root / "contracts" / "executable-trust-v1.0.yaml").read_text(encoding="utf-8")
    )
    source["verification"]["fail_closed"] = False
    broken = tmp_path / "failopen.yaml"
    broken.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ContractValidationError):
        load_contract(broken)


def test_contract_with_a_third_strategy_is_rejected(tmp_path, repo_root):
    """ET-OUT-002: REFUSED may not be added as a strategy.

    Pinned at the artifact level as well as in code, because the tidy-the-schema
    pressure usually arrives as a contract edit first.
    """
    source = yaml.safe_load(
        (repo_root / "contracts" / "executable-trust-v1.0.yaml").read_text(encoding="utf-8")
    )
    source["vocabulary"]["response_strategies"].append("REFUSAL")
    broken = tmp_path / "threestrategies.yaml"
    broken.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ContractValidationError):
        load_contract(broken)


def test_contract_vocabulary_must_match_the_code(tmp_path, repo_root):
    """ET-CON-003: contract and implementation disagreeing is a defect in one of them.

    Two layers guard this and the schema happens to catch it first, which is
    why the assertion is on the exception type rather than a message. The
    code-level check in the loader remains as defence in depth for the case
    where the schema's enum is later widened: a contract could then declare a
    verdict the decision function has no branch for.
    """
    source = yaml.safe_load(
        (repo_root / "contracts" / "executable-trust-v1.0.yaml").read_text(encoding="utf-8")
    )
    source["vocabulary"]["claim_verdicts"] = ["SUPPORTED", "UNSUPPORTED"]
    broken = tmp_path / "vocab.yaml"
    broken.write_text(yaml.safe_dump(source), encoding="utf-8")

    with pytest.raises(ContractValidationError):
        load_contract(broken)


# ---------------------------------------------------------------------------
# ET-CON-004 — controlled reason codes
# ---------------------------------------------------------------------------


def test_uncontrolled_reason_code_is_rejected(registry: ContractRegistry):
    """ET-CON-004: the answer to a missing code is an amendment, not a new string."""
    with pytest.raises(UncontrolledReasonCode, match="amendment"):
        registry.require_controlled_reason_code("something_i_just_made_up")


def test_every_implemented_reason_code_is_declared(registry: ContractRegistry):
    """ET-CON-004: the enum and the contract set match exactly, both directions."""
    declared = set(registry.reason_codes)
    implemented = {c.value for c in ReasonCode}

    assert declared == implemented


def test_every_reason_code_traces_to_a_rule(registry: ContractRegistry):
    """ET-CON-004: a code that explains nothing traceable is not controlled."""
    rule_ids = set()
    for cid, ver in registry.registered():
        rule_ids |= registry.get(cid, ver).all_rule_ids()

    for code, entry in registry.reason_codes.items():
        assert entry["rule_id"] in rule_ids, f"{code} names an unknown rule"


def test_registry_cross_validation_passes(registry: ContractRegistry):
    """ET-CON-004: the full cross-artifact check suite is clean."""
    report = validate_registry(registry)

    assert report.ok, report.errors
    assert report.checks_run > 50


# ---------------------------------------------------------------------------
# Amendments
# ---------------------------------------------------------------------------


def test_amendment_loads_and_validates():
    """ET-CON-003: amendments satisfy their schema and their model invariants."""
    amendments = load_amendments()

    assert len(amendments) == 1
    assert amendments[0].amendment_id == "v1.0-A1"
    assert amendments[0].is_ratified


def test_amendment_preserves_the_prior_contract_version(repo_root):
    """ET-CON-002: an amendment never rewrites the version it amends.

    Checked on the filesystem, not the registry: the claim is about the durable
    artifact that explains historical decisions.
    """
    amendments = load_amendments()
    assert_prior_versions_preserved(amendments)

    assert contract_path_for("1.0").is_file()


def test_amendment_records_its_accepted_trade_off():
    """An amendment claiming no cost is usually not being honest about one."""
    amendment = load_amendments()[0]

    assert amendment.accepted_trade_off
    assert amendment.forward_constraint
    assert "verification" in amendment.forward_constraint.lower()


def test_author_may_not_ratify_their_own_amendment():
    """Authorship is not ratification."""
    base = load_amendments()[0].model_dump()
    base["ratifier"] = base["author"]

    with pytest.raises(ValueError, match="authorship is not ratification"):
        ContractAmendment.model_validate(base)


def test_amendment_must_move_the_version_forward():
    """A backwards amendment is a rollback pretending to be a change."""
    base = load_amendments()[0].model_dump()
    base["new_contract_version"] = "0.9"

    with pytest.raises(ValueError, match="not forward"):
        ContractAmendment.model_validate(base)


def test_amendment_naming_an_unknown_rule_is_rejected(registry: ContractRegistry):
    """An amendment cannot document a change to a rule that was never there."""
    base = load_amendments()[0].model_dump(mode="json")
    # Assembled at runtime: a literal here would read as a real rule reference
    # to the traceability scanner, which scans raw test source.
    base["affected_rule_ids"] = ["ET-VER-" + "999"]

    with pytest.raises(ContractValidationError, match="absent from"):
        registry.register_amendment(base)


def test_registered_version_content_is_fixed(registry: ContractRegistry, repo_root):
    """A version's content is fixed once registered; changes publish a new version."""
    contract = registry.get(CONTRACT_ID, "1.0")
    mutated = contract.model_copy(update={"raw": {**contract.raw, "title": "changed"}})

    with pytest.raises(ContractValidationError, match="already registered"):
        registry.register(mutated)


# ---------------------------------------------------------------------------
# ET-EVAL-001 / ET-EVAL-002 — the evaluation contract
# ---------------------------------------------------------------------------


def test_baseline_gate_is_declared(contract):
    """ET-EVAL-001: the gate threshold is contract configuration, not a constant."""
    rule = contract.rule("ET-EVAL-001")

    assert rule is not None
    assert rule.minimum_pass_rate == 1.0  # type: ignore[attr-defined]


def test_offline_owns_correctness(contract):
    """ET-EVAL-002: runtime records what it decided, never whether it was right."""
    rule = contract.rule("ET-EVAL-002")

    assert rule is not None
    assert "ground truth" in rule.statement


def test_minimum_sample_comes_from_the_contract(contract):
    """ET-TEL-005: the threshold is reviewable by the people accountable for it."""
    assert contract.minimum_sample() == 10


def test_registry_is_rebuildable_deterministically():
    """Two registries built from the same files are equivalent."""
    a, b = build_default_registry(), build_default_registry()

    assert a.registered() == b.registered()
    assert a.reason_codes == b.reason_codes
