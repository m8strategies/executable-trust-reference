"""Load and schema-validate contract, reason-code, and amendment artifacts.

Loading is where the contract stops being a document and becomes something the
runtime can be measured against. Three checks run here, in order, and all three
fail closed:

1. The YAML parses.
2. It validates against the JSON Schema.
3. Its declared vocabulary matches the vocabulary the code implements.

The third check is the one that is easy to leave out and expensive to omit. A
contract that declares a response strategy the code does not implement is not a
contract the code can honour, and discovering that at the first request rather
than at load time means discovering it in production.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

import yaml
from jsonschema import Draft202012Validator

from executable_trust.contracts.models import TrustContract
from executable_trust.domain.enums import (
    ClaimVerdict,
    DecisionOutcome,
    ReasonCode,
    ResponseStrategy,
)
from executable_trust.domain.errors import ContractValidationError

#: Repository root, derived from this file's location rather than the working
#: directory, so the loader behaves the same however the process was started.
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_DIR = PACKAGE_ROOT / "schemas"
CONTRACT_DIR = PACKAGE_ROOT / "contracts"
AMENDMENT_DIR = CONTRACT_DIR / "amendments"


@cache
def load_schema(name: str) -> dict[str, Any]:
    """Load a JSON Schema by file name, cached for the process lifetime."""
    path = SCHEMA_DIR / name
    if not path.is_file():
        raise ContractValidationError(f"schema not found: {path}")
    with path.open(encoding="utf-8") as fh:
        data: dict[str, Any] = json.load(fh)
    return data


def validate_against_schema(instance: object, schema_name: str, *, source: str) -> None:
    """Validate ``instance``, reporting *every* violation rather than the first.

    Reporting one error at a time turns fixing a contract into a guessing game.
    """
    validator = Draft202012Validator(load_schema(schema_name))
    errors = sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path))
    if errors:
        detail = "; ".join(
            f"{'/'.join(str(p) for p in e.absolute_path) or '<root>'}: {e.message}" for e in errors
        )
        raise ContractValidationError(f"{source} failed schema validation: {detail}")


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ContractValidationError(f"artifact not found: {path}")
    try:
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except yaml.YAMLError as exc:
        raise ContractValidationError(f"{path.name} is not parseable YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ContractValidationError(f"{path.name} must contain a mapping at the top level")
    return data


def _check_vocabulary_matches_code(contract: TrustContract) -> None:
    """Fail closed when the contract and the implementation disagree.

    Both claim to implement one specification. If they disagree, one of them
    has a defect — it is not a difference of professional opinion to be
    resolved by preferring whichever is more convenient at runtime.
    """
    expected: tuple[tuple[str, set[str], set[str]], ...] = (
        (
            "claim_verdicts",
            {v.value for v in contract.vocabulary.claim_verdicts},
            {v.value for v in ClaimVerdict},
        ),
        (
            "decision_outcomes",
            {o.value for o in contract.vocabulary.decision_outcomes},
            {o.value for o in DecisionOutcome},
        ),
        (
            "response_strategies",
            {s.value for s in contract.vocabulary.response_strategies},
            {s.value for s in ResponseStrategy},
        ),
    )
    for field, declared, implemented in expected:
        if declared != implemented:
            raise ContractValidationError(
                f"contract {contract.contract_id} v{contract.version} declares "
                f"{field}={sorted(declared)} but the implementation provides "
                f"{sorted(implemented)}; contract and code must agree"
            )


def load_contract(path: Path | str) -> TrustContract:
    """Load, validate, and type one trust contract.

    Does **not** check ratification: loading a draft contract in order to
    inspect it is legitimate. Whether a contract may *govern* is a separate
    question, answered by the registry at resolution time.
    """
    path = Path(path)
    data = _read_yaml(path)
    validate_against_schema(data, "trust-contract.schema.json", source=path.name)
    contract = TrustContract.model_validate({**data, "raw": data})
    _check_vocabulary_matches_code(contract)
    return contract


def load_reason_codes(path: Path | str) -> dict[str, dict[str, Any]]:
    """Load the controlled reason-code set, keyed by code.

    Cross-checks the declared set against :class:`ReasonCode` in both
    directions. A code in the contract that the enum lacks would be
    unemittable; a code in the enum that the contract lacks could be emitted
    and would then be uncontrolled. Both are defects.
    """
    path = Path(path)
    data = _read_yaml(path)
    entries = data.get("codes")
    if not isinstance(entries, list) or not entries:
        raise ContractValidationError(f"{path.name} declares no reason codes")

    codes: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict) or "code" not in entry:
            raise ContractValidationError(f"{path.name} contains a malformed reason-code entry")
        code = str(entry["code"])
        if code in codes:
            raise ContractValidationError(f"{path.name} declares duplicate reason code {code!r}")
        if not entry.get("rule_id"):
            raise ContractValidationError(
                f"reason code {code!r} declares no rule_id; every code must trace to a rule"
            )
        codes[code] = entry

    declared = set(codes)
    implemented = {c.value for c in ReasonCode}
    if declared != implemented:
        missing = sorted(implemented - declared)
        extra = sorted(declared - implemented)
        raise ContractValidationError(
            "reason-code set and implementation disagree: "
            f"declared-but-not-implemented={extra}, implemented-but-not-declared={missing}"
        )
    return codes


def load_amendment(path: Path | str) -> dict[str, Any]:
    """Load and schema-validate one contract amendment."""
    path = Path(path)
    data = _read_yaml(path)
    validate_against_schema(data, "contract-amendment.schema.json", source=path.name)
    return data


def discover_contracts(directory: Path | str = CONTRACT_DIR) -> list[Path]:
    """Return contract files in ``directory``, excluding amendments.

    Sorted, because a deterministic load order keeps a registry built from a
    directory reproducible.
    """
    directory = Path(directory)
    return sorted(p for p in directory.glob("*.yaml") if p.is_file())


def discover_amendments(directory: Path | str = AMENDMENT_DIR) -> list[Path]:
    """Return amendment files in ``directory``."""
    directory = Path(directory)
    if not directory.is_dir():
        return []
    return sorted(p for p in directory.glob("*.yaml") if p.is_file())
