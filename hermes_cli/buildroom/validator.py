"""Validate Hermes Buildroom contract rooms.

The validator is read-only: it parses JSON artifacts, checks schema/order/chain
consistency, and returns an in-memory report. It never creates Kanban tasks or
mutates runtime Hermes state.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .schemas import ARTIFACT_ENVELOPE_MODELS, REQUIRED_ARTIFACT_ORDER, BaseArtifact


@dataclass(slots=True)
class BuildroomValidationReport:
    valid: bool
    room_path: str
    chain_id: str | None = None
    artifact_count: int = 0
    artifact_types: list[str] = field(default_factory=list)
    contract_ids: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class LoadedArtifact:
    path: Path
    artifact: BaseArtifact


def validate_room(room_path: str | Path) -> BuildroomValidationReport:
    """Validate every JSON contract artifact in a Buildroom room directory."""

    room = Path(room_path)
    errors: list[str] = []
    warnings: list[str] = []
    loaded: list[LoadedArtifact] = []

    if not room.exists():
        return BuildroomValidationReport(
            valid=False,
            room_path=str(room),
            errors=[f"room does not exist: {room}"],
        )
    if not room.is_dir():
        return BuildroomValidationReport(
            valid=False,
            room_path=str(room),
            errors=[f"room is not a directory: {room}"],
        )

    json_paths = sorted(room.glob("*.json"))
    if not json_paths:
        errors.append(f"no JSON artifacts found in {room}")

    for path in json_paths:
        data = _read_json(path, errors)
        if data is None:
            continue
        artifact_type = data.get("artifact_type")
        model = ARTIFACT_ENVELOPE_MODELS.get(artifact_type)
        if model is None:
            errors.append(
                f"{path.name}: unknown or missing artifact_type {artifact_type!r}; "
                "schema presence cannot be confirmed"
            )
            continue
        try:
            loaded.append(LoadedArtifact(path=path, artifact=model.model_validate(data)))
        except ValidationError as exc:
            errors.extend(_format_validation_errors(path.name, artifact_type, exc))

    artifact_types = [item.artifact.artifact_type for item in loaded]
    contract_ids = [item.artifact.contract_id for item in loaded]
    chain_id = loaded[0].artifact.chain_id if loaded else None

    _check_required_order(artifact_types, errors)
    _check_filename_order(loaded, errors)
    _check_chain_and_parent_consistency(loaded, errors)
    _check_terminal_states(loaded, errors)
    _check_duplicate_contract_ids(contract_ids, errors)

    return BuildroomValidationReport(
        valid=not errors,
        room_path=str(room),
        chain_id=chain_id,
        artifact_count=len(loaded),
        artifact_types=artifact_types,
        contract_ids=contract_ids,
        errors=errors,
        warnings=warnings,
    )


def load_validated_artifacts(room_path: str | Path) -> list[BaseArtifact]:
    """Return typed artifacts or raise ValueError with validation details."""

    report = validate_room(room_path)
    if not report.valid:
        raise ValueError("buildroom validation failed: " + "; ".join(report.errors))

    artifacts: list[BaseArtifact] = []
    for path in sorted(Path(room_path).glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        model = ARTIFACT_ENVELOPE_MODELS[data["artifact_type"]]
        artifacts.append(model.model_validate(data))
    return artifacts


def _read_json(path: Path, errors: list[str]) -> dict[str, Any] | None:
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        errors.append(f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}")
        return None
    if not isinstance(data, dict):
        errors.append(f"{path.name}: artifact must be a JSON object")
        return None
    return data


def _format_validation_errors(
    file_name: str, artifact_type: str | None, exc: ValidationError
) -> list[str]:
    prefix = artifact_type or "unknown-artifact"
    formatted: list[str] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error.get("loc", ()))
        formatted.append(f"{file_name}: {prefix}.{location}: {error['msg']}")
    return formatted


def _check_required_order(artifact_types: list[str], errors: list[str]) -> None:
    expected = list(REQUIRED_ARTIFACT_ORDER)
    if artifact_types == expected:
        return

    missing = [artifact_type for artifact_type in expected if artifact_type not in artifact_types]
    extra = [artifact_type for artifact_type in artifact_types if artifact_type not in expected]
    if missing:
        errors.append(f"missing required artifacts: {', '.join(missing)}")
    if extra:
        errors.append(f"unexpected artifacts: {', '.join(extra)}")
    if not missing and not extra:
        errors.append(
            "artifacts are out of required order: "
            f"expected {expected}, got {artifact_types}"
        )


def _check_filename_order(loaded: list[LoadedArtifact], errors: list[str]) -> None:
    for index, item in enumerate(loaded, start=1):
        expected_prefix = f"{index:02d}-"
        if not item.path.name.startswith(expected_prefix):
            errors.append(
                f"{item.path.name}: expected filename prefix {expected_prefix!r} "
                f"for {item.artifact.artifact_type}"
            )


def _check_chain_and_parent_consistency(
    loaded: list[LoadedArtifact], errors: list[str]
) -> None:
    if not loaded:
        return

    chain_id = loaded[0].artifact.chain_id
    previous_contract_id: str | None = None
    for index, item in enumerate(loaded):
        artifact = item.artifact
        if artifact.chain_id != chain_id:
            errors.append(
                f"{item.path.name}: chain_id {artifact.chain_id!r} does not match "
                f"room chain_id {chain_id!r}"
            )
        if index == 0:
            if artifact.parent_id is not None:
                errors.append(
                    f"{item.path.name}: first artifact parent_id must be null/None"
                )
        elif artifact.parent_id != previous_contract_id:
            errors.append(
                f"{item.path.name}: parent_id {artifact.parent_id!r} must match "
                f"previous contract_id {previous_contract_id!r}"
            )
        previous_contract_id = artifact.contract_id


def _check_terminal_states(loaded: list[LoadedArtifact], errors: list[str]) -> None:
    by_type = {item.artifact.artifact_type: item.artifact for item in loaded}
    delta = by_type.get("verification-delta")
    trust = by_type.get("trust-report")
    retention = by_type.get("retention-review")
    qa = by_type.get("qa-verification")
    intent = by_type.get("intent-review")
    main = by_type.get("main-review")
    verification = by_type.get("verification")
    product_plan = by_type.get("product-plan")

    if delta is not None and delta.payload.delta_state == "none" and delta.payload.required_actions:
        errors.append(
            "verification-delta: required_actions must be empty when delta_state is 'none'"
        )
    if trust is not None:
        trust_is_trusted = trust.payload.trust_state == "trusted"
        if trust_is_trusted and not trust.payload.independent_qa_confirmed:
            errors.append("trust-report: trust_state 'trusted' requires independent_qa_confirmed=true")
        if trust_is_trusted and intent is not None and intent.payload.decision != "approved":
            errors.append("trust-report: trust_state 'trusted' requires intent-review decision 'approved'")
        if trust_is_trusted and main is not None and main.payload.decision != "aligned":
            errors.append("trust-report: trust_state 'trusted' requires main-review decision 'aligned'")
        if trust_is_trusted and verification is not None and verification.payload.status != "passed":
            errors.append("trust-report: trust_state 'trusted' requires verification status 'passed'")
        if trust_is_trusted and qa is not None and qa.payload.state != "passed":
            errors.append("trust-report: cannot be trusted when qa-verification did not pass")
        if trust_is_trusted and delta is not None and delta.payload.delta_state in {"open", "rejected"}:
            errors.append(
                "trust-report: trust_state 'trusted' requires verification-delta "
                f"not be {delta.payload.delta_state!r}"
            )

    if main is not None and main.payload.risk_band == 3:
        errors.append("main-review: risk_band 3 is forbidden for autonomous build")

    if product_plan is not None:
        allowed = set(product_plan.payload.allowed_paths)
        protected = set(product_plan.payload.protected_surfaces)
        forbidden_overlap = allowed & protected
        if forbidden_overlap:
            errors.append(f"product-plan: allowed_paths contains protected_surfaces: {', '.join(sorted(forbidden_overlap))}")

    if retention is not None and retention.payload.retention_state == "discard":
        errors.append("retention-review: demo/runtime room cannot end in discard state")


def _check_duplicate_contract_ids(contract_ids: list[str], errors: list[str]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for contract_id in contract_ids:
        if contract_id in seen:
            duplicates.add(contract_id)
        seen.add(contract_id)
    if duplicates:
        errors.append(f"duplicate contract_id values: {', '.join(sorted(duplicates))}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate a Hermes Buildroom room")
    parser.add_argument("room", type=Path, help="Path to a buildroom directory")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print the full validation report as JSON instead of CLEAN/ERROR lines",
    )
    args = parser.parse_args(argv)

    report = validate_room(args.room)
    if args.json:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    elif report.valid:
        print(f"CLEAN buildroom: {report.chain_id} ({report.artifact_count} artifacts)")
    else:
        print(f"ERROR buildroom: {args.room}")
        for error in report.errors:
            print(f"- {error}")
    return 0 if report.valid else 1


if __name__ == "__main__":  # pragma: no cover - exercised by smoke tests
    raise SystemExit(main())
