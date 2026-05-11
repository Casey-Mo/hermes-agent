import json
import shutil
from pathlib import Path

from hermes_cli.buildroom.summary import build_operator_summary
from hermes_cli.buildroom.validator import REQUIRED_ARTIFACT_ORDER, validate_room


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "buildroom" / "demo-chain"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def test_demo_fixture_validates_full_contract_chain_and_operator_summary_is_sanitized():
    report = validate_room(FIXTURE_DIR)

    assert report.valid is True
    assert report.errors == []
    assert report.artifact_count == len(REQUIRED_ARTIFACT_ORDER)
    assert report.artifact_types == list(REQUIRED_ARTIFACT_ORDER)
    assert report.chain_id == "demo-buildroom-0"

    summary = build_operator_summary(FIXTURE_DIR)

    assert summary["chain_id"] == "demo-buildroom-0"
    assert summary["status"] == "clean"
    assert summary["trust_state"] == "trusted"
    assert summary["delta_state"] == "none"
    assert summary["retention_state"] == "retain"
    assert summary["artifact_count"] == len(REQUIRED_ARTIFACT_ORDER)
    assert "manual adapter wiring" in " ".join(summary["next_actions"])
    serialized = json.dumps(summary).lower()
    assert "api_key" not in serialized
    assert "secret" not in serialized
    assert "token" not in serialized


def test_validator_rejects_missing_qa_evidence(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    qa_path = room / "08-qa-verification.json"
    qa = _load_json(qa_path)
    qa["payload"].pop("evidence")
    _write_json(qa_path, qa)

    report = validate_room(room)

    assert report.valid is False
    assert any("qa-verification" in error and "evidence" in error for error in report.errors)


def test_validator_rejects_invalid_trust_and_delta_states(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    delta_path = room / "09-verification-delta.json"
    delta = _load_json(delta_path)
    delta["payload"]["delta_state"] = "surprised"
    _write_json(delta_path, delta)
    trust_path = room / "10-trust-report.json"
    trust = _load_json(trust_path)
    trust["payload"]["trust_state"] = "maybe"
    _write_json(trust_path, trust)

    report = validate_room(room)

    assert report.valid is False
    assert any("verification-delta" in error and "delta_state" in error for error in report.errors)
    assert any("trust-report" in error and "trust_state" in error for error in report.errors)


def test_validator_requires_bounded_product_plan_guardrails(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    plan_path = room / "05-product-plan.json"
    plan = _load_json(plan_path)
    plan["payload"].pop("allowed_paths")
    _write_json(plan_path, plan)

    report = validate_room(room)

    assert report.valid is False
    assert any("product-plan" in error and "allowed_paths" in error for error in report.errors)


def test_operator_summary_redacts_secret_like_values(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    summary_path = room / "12-operator-summary.json"
    operator = _load_json(summary_path)
    secret = "sk-THIS_IS_A_SECRET_VALUE_THAT_MUST_NOT_LEAK_1234567890"
    operator["payload"]["next_actions"].append(f"investigate {secret}")
    _write_json(summary_path, operator)

    summary = build_operator_summary(room)

    serialized = json.dumps(summary)
    assert secret not in serialized
    assert "THIS_IS_A_SECRET" not in serialized
    assert "[redacted-value]" in serialized
