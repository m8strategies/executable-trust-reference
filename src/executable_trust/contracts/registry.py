"""Contract resolution: which contract governs this request, if any.

Resolution is the single place where "may this contract govern a decision" is
answered, so no caller can forget to ask. Three fail-closed paths:

- an unknown version raises :class:`~executable_trust.domain.errors.ContractNotFound`;
- an unratified contract raises :class:`~executable_trust.domain.errors.ContractNotRatified`;
- an unregistered contract identifier raises the same as an unknown version.

Registering a contract and resolving one are deliberately separate operations.
A draft contract can be registered and inspected; it simply cannot govern.

**Scope note.** This registry resolves per request from an in-memory map. A
system that stores contracts and ratification acts in a transactional database
faces an additional problem this reference cannot demonstrate — the act that
ratifies a new version is itself a governed write, so it sits on the boundary
between two regimes. See the *Contract Activation Boundary Semantics* section
of ``docs/architecture.md``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from executable_trust.contracts.loader import (
    CONTRACT_DIR,
    discover_amendments,
    load_amendment,
    load_contract,
    load_reason_codes,
)
from executable_trust.contracts.models import TrustContract
from executable_trust.domain.errors import (
    ContractNotFound,
    ContractNotRatified,
    ContractValidationError,
    UncontrolledReasonCode,
)


class ContractRegistry:
    """Holds every known contract version and the controlled reason-code set.

    Versions accumulate rather than replace. Registering v1.1 does not remove
    v1.0: decisions recorded under v1.0 named that version, and the rules they
    were judged by must remain readable. An amendment supersedes a version's
    *authority*, never its *record*.
    """

    def __init__(self) -> None:
        self._contracts: dict[tuple[str, str], TrustContract] = {}
        self._reason_codes: dict[str, dict[str, Any]] = {}
        self._amendments: dict[str, dict[str, Any]] = {}

    # -- registration ------------------------------------------------------

    def register(self, contract: TrustContract) -> None:
        """Add a contract version. Re-registering an identical version is a no-op."""
        key = contract.key
        existing = self._contracts.get(key)
        if existing is not None and existing.raw != contract.raw:
            raise ContractValidationError(
                f"contract {key[0]} v{key[1]} is already registered with different content; "
                "a version's content is fixed once registered — publish a new version instead"
            )
        self._contracts[key] = contract

    def register_reason_codes(self, codes: dict[str, dict[str, Any]]) -> None:
        self._reason_codes = dict(codes)

    def register_amendment(self, amendment: dict[str, Any]) -> None:
        """Record an amendment and verify it references a contract that exists.

        An amendment naming a rule the contract does not declare is rejected:
        it would document a change to something that was never there.
        """
        amendment_id = str(amendment["amendment_id"])
        contract_id = str(amendment["contract_id"])
        previous = str(amendment["previous_contract_version"])

        base = self._contracts.get((contract_id, previous))
        if base is None:
            raise ContractValidationError(
                f"amendment {amendment_id} amends {contract_id} v{previous}, "
                "which is not registered"
            )
        declared = base.all_rule_ids()
        unknown = [rid for rid in amendment["affected_rule_ids"] if rid not in declared]
        if unknown:
            raise ContractValidationError(
                f"amendment {amendment_id} names rule ids absent from "
                f"{contract_id} v{previous}: {sorted(unknown)}"
            )
        self._amendments[amendment_id] = amendment

    # -- resolution --------------------------------------------------------

    def get(self, contract_id: str, version: str) -> TrustContract:
        """Return a registered contract without checking ratification."""
        contract = self._contracts.get((contract_id, version))
        if contract is None:
            raise ContractNotFound(
                f"no contract registered for {contract_id!r} v{version!r}; "
                f"known versions: {sorted(v for cid, v in self._contracts if cid == contract_id)}"
            )
        return contract

    def resolve(self, contract_id: str, version: str) -> TrustContract:
        """Return the contract that will govern a decision.

        This is the gate. An unknown or unratified contract never reaches the
        decision function.
        """
        contract = self.get(contract_id, version)
        if not contract.is_ratified:
            raise ContractNotRatified(
                f"contract {contract_id} v{version} has ratification status "
                f"{contract.ratification.status.value!r} and may not govern a decision; "
                "only a ratified contract governs"
            )
        return contract

    # -- controlled reason codes -------------------------------------------

    def require_controlled_reason_code(self, code: str) -> None:
        """Raise unless ``code`` is declared in the controlled set."""
        if code not in self._reason_codes:
            raise UncontrolledReasonCode(
                f"reason code {code!r} is not declared in the controlled reason-code set; "
                "the correct response to a missing code is a contract amendment"
            )

    @property
    def reason_codes(self) -> dict[str, dict[str, Any]]:
        return dict(self._reason_codes)

    @property
    def amendments(self) -> dict[str, dict[str, Any]]:
        return dict(self._amendments)

    def registered(self) -> list[tuple[str, str]]:
        """Every registered ``(contract_id, version)`` pair, sorted.

        Includes unratified versions: validation and traceability are
        privileged consumers that must see every version, not only the
        governing ones.
        """
        return sorted(self._contracts)

    def versions(self, contract_id: str) -> list[str]:
        """Registered versions of ``contract_id``, sorted numerically."""
        found = [v for cid, v in self._contracts if cid == contract_id]
        return sorted(found, key=lambda v: tuple(int(p) for p in v.split(".")))


def build_default_registry(contract_dir: Path | str = CONTRACT_DIR) -> ContractRegistry:
    """Build a registry from the repository's contract directory.

    Loads every contract version, the controlled reason-code set, and every
    amendment. Amendments load last because registering one validates it
    against the contract it amends.
    """
    contract_dir = Path(contract_dir)
    registry = ContractRegistry()

    for path in sorted(contract_dir.glob("executable-trust-v*.yaml")):
        registry.register(load_contract(path))

    reason_code_files = sorted(contract_dir.glob("reason-codes-v*.yaml"))
    if not reason_code_files:
        raise ContractValidationError(f"no reason-code set found in {contract_dir}")
    registry.register_reason_codes(load_reason_codes(reason_code_files[-1]))

    for path in discover_amendments(contract_dir / "amendments"):
        registry.register_amendment(load_amendment(path))

    return registry
