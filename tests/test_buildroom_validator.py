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


def test_validator_rejects_band_3_autonomous_build(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    main_path = room / "04-main-review.json"
    main = _load_json(main_path)
    main["payload"]["risk_band"] = 3
    _write_json(main_path, main)

    report = validate_room(room)

    assert report.valid is False
    assert any("risk_band 3" in error and "forbidden" in error for error in report.errors)


def test_validator_rejects_allowed_path_protected_surface_overlap(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    plan_path = room / "05-product-plan.json"
    plan = _load_json(plan_path)
    overlap = plan["payload"]["protected_surfaces"][0]
    plan["payload"]["allowed_paths"].append(overlap)
    _write_json(plan_path, plan)

    report = validate_room(room)

    assert report.valid is False
    assert any("allowed_paths contains protected_surfaces" in error for error in report.errors)


def test_validator_rejects_trusted_state_when_intent_is_rejected(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    intent_path = room / "03-intent-review.json"
    intent = _load_json(intent_path)
    intent["payload"]["decision"] = "rejected"
    _write_json(intent_path, intent)

    report = validate_room(room)

    assert report.valid is False
    assert any(
        "trust-report" in error and "intent-review" in error and "approved" in error
        for error in report.errors
    )


def test_validator_rejects_trusted_state_when_main_is_not_aligned(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    main_path = room / "04-main-review.json"
    main = _load_json(main_path)
    main["payload"]["decision"] = "not-aligned"
    _write_json(main_path, main)

    report = validate_room(room)

    assert report.valid is False
    assert any(
        "trust-report" in error and "main-review" in error and "aligned" in error
        for error in report.errors
    )


def test_validator_rejects_trusted_state_when_verification_failed(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    verification_path = room / "07-verification.json"
    verification = _load_json(verification_path)
    verification["payload"]["status"] = "failed"
    _write_json(verification_path, verification)

    report = validate_room(room)

    assert report.valid is False
    assert any(
        "trust-report" in error and "verification" in error and "passed" in error
        for error in report.errors
    )


def test_validator_rejects_trusted_state_when_delta_is_open(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    delta_path = room / "09-verification-delta.json"
    delta = _load_json(delta_path)
    delta["payload"]["delta_state"] = "open"
    delta["payload"]["required_actions"] = ["resolve remaining verification gap"]
    _write_json(delta_path, delta)

    report = validate_room(room)

    assert report.valid is False
    assert any(
        "trust-report" in error and "verification-delta" in error and "open" in error
        for error in report.errors
    )


def test_validator_rejects_trusted_state_when_delta_is_rejected(tmp_path):
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    delta_path = room / "09-verification-delta.json"
    delta = _load_json(delta_path)
    delta["payload"]["delta_state"] = "rejected"
    delta["payload"]["required_actions"] = ["replace rejected verification evidence"]
    _write_json(delta_path, delta)

    report = validate_room(room)

    assert report.valid is False
    assert any(
        "trust-report" in error and "verification-delta" in error and "rejected" in error
        for error in report.errors
    )


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


def test_operator_summary_redacts_bearer_tokens(tmp_path):
    """Bearer tokens embedded in summary text must be redacted by SECRET_VALUE_PATTERNS."""
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    summary_path = room / "12-operator-summary.json"
    operator = _load_json(summary_path)
    bearer_token = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.payload.signature"
    operator["payload"]["summary"] = f"handoff header {bearer_token}"
    _write_json(summary_path, operator)

    summary = build_operator_summary(room)

    serialized = json.dumps(summary)
    assert bearer_token not in serialized
    assert "[redacted-value]" in serialized


def test_operator_summary_redacts_authorization_and_bearer_in_string_values(tmp_path):
    """String values containing 'authorization' or 'bearer' must be redacted by marker-substitution."""
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    summary_path = room / "12-operator-summary.json"
    operator = _load_json(summary_path)
    operator["payload"]["summary"] = "Authorization header was Bearer abcdefg but that is secret"
    _write_json(summary_path, operator)

    summary = build_operator_summary(room)

    serialized = json.dumps(summary)
    assert "Authorization" not in serialized
    assert "Bearer abcdefg" not in serialized
    assert "[redacted-marker]" in serialized
