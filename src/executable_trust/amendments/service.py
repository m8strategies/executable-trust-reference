"""Amendment loading and the prior-version-preservation check.

The invariant this module exists to enforce: **an amendment never rewrites the
contract it amends.** The prior version file stays on disk, unmodified, and
continues to govern the decisions that named it. Rewriting it would make every
historical decision unexplainable, because the rules it was judged by would no
longer exist anywhere.
"""

from __future__ import annotations

from pathlib import Path

from executable_trust.amendments.models import ContractAmendment
from executable_trust.contracts.loader import (
    AMENDMENT_DIR,
    CONTRACT_DIR,
    discover_amendments,
    load_amendment,
)
from executable_trust.domain.errors import ContractValidationError


def load_amendments(directory: Path | str = AMENDMENT_DIR) -> tuple[ContractAmendment, ...]:
    """Load and type every amendment in ``directory``, sorted by identifier."""
    amendments = [
        ContractAmendment.model_validate(load_amendment(path))
        for path in discover_amendments(directory)
    ]
    return tuple(sorted(amendments, key=lambda a: a.amendment_id))


def contract_path_for(version: str, *, contract_dir: Path | str = CONTRACT_DIR) -> Path:
    """Path of the contract file for ``version``."""
    return Path(contract_dir) / f"executable-trust-v{version}.yaml"


def assert_prior_versions_preserved(
    amendments: tuple[ContractAmendment, ...],
    *,
    contract_dir: Path | str = CONTRACT_DIR,
) -> None:
    """Raise unless every amended contract version still exists on disk.

    Checks the filesystem rather than the registry deliberately. A registry
    built in this process could hold a version whose file was deleted; the
    claim being made is about the durable artifact, not about what happens to
    be in memory.
    """
    for amendment in amendments:
        path = contract_path_for(amendment.previous_contract_version, contract_dir=contract_dir)
        if not path.is_file():
            raise ContractValidationError(
                f"amendment {amendment.amendment_id} amends contract version "
                f"v{amendment.previous_contract_version}, but {path.name} is not present. "
                "An amendment never rewrites or removes the version it amends: decisions "
                "recorded under that version must remain explainable."
            )


def amendments_for(
    amendments: tuple[ContractAmendment, ...], contract_version: str
) -> tuple[ContractAmendment, ...]:
    """Amendments that amend ``contract_version``."""
    return tuple(a for a in amendments if a.previous_contract_version == contract_version)
