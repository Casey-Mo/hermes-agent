"""Tests for the research-to-buildroom adapter (buildroom.handoff)."""

import json
import shutil
from pathlib import Path

import pytest

from hermes_cli.buildroom.handoff import (
    ResearchInputBuilder,
    SubcHandoffInput,
    build_dry_run_room,
    synthesize_idea_contract,
)

FIXTURE_HANDOFF_DIR = Path(__file__).parent / "fixtures" / "buildroom" / "fixture-handoff"
FIXTURE_HANDOFF_PATH = FIXTURE_HANDOFF_DIR / "subc-handoff.json"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# --- RED: tests for the adapter input model ---


def test_subc_handoff_input_validates_real_shaped_data():
    """The input model should parse a fixture shaped like the real subc-handoff.json."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    assert parsed.updated_at is not None
    assert parsed.run_id is not None
    assert len(parsed.items) >= 1
    assert parsed.items[0].topic is not None
    assert parsed.items[0].signal is not None


def test_subc_handoff_input_rejects_empty_items():
    """An empty items list is not useful; the model should still parse but builder
    should later reject it."""
    data = {"updated_at": "2026-05-10T20:19:17-05:00", "run_id": "t-000", "items": []}
    parsed = SubcHandoffInput.model_validate(data)
    assert len(parsed.items) == 0


# --- RED: tests for the research-input builder ---


def test_research_input_builder_uses_signal_titles():
    """ResearchInputBuilder should produce a ResearchInputPayload using the subc
    handoff topics as signals and signals text as evidence."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    payload = ResearchInputBuilder.build(parsed, chain_id="test-chain-0", contract_id="tc-01")

    assert payload.title is not None
    assert len(payload.signals) >= 1
    assert len(payload.evidence) >= 1
    assert len(payload.constraints) >= 1
    # Topics appear as signal entries
    assert any("hermes-cron" in s or "xurl" in s or "open-brain" in s for s in payload.signals)
    # Evidence entries include actual signal text
    assert any(len(s) > 10 for s in payload.evidence)


def test_research_input_builder_article_chain_id_stable():
    """Two calls with the same data produce identical chain_ids."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    p1 = ResearchInputBuilder.build(parsed, chain_id="chain-v1", contract_id="c-01")
    p2 = ResearchInputBuilder.build(parsed, chain_id="chain-v1", contract_id="c-01")

    assert p1.title == p2.title
    assert p1.signals == p2.signals


# --- RED: tests for the idea-contract synthesizer ---


def test_idea_contract_synthesizer_produces_valid_payload():
    """synthesize_idea_contract should produce a valid IdeaContractPayload from
    a subc handoff."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    payload = synthesize_idea_contract(
        parsed,
        chain_id="test-chain-0",
        contract_id="tc-02",
        parent_id="tc-01",
        research_refs=["tc-01"],
    )

    assert payload.title is not None
    assert len(payload.problem_statement) > 0
    assert len(payload.proposed_solution) > 0
    assert len(payload.estimated_impact) > 0
    assert len(payload.research_refs) >= 1


def test_idea_contract_rejects_empty_handoff():
    """An empty subc handoff should still produce a valid but minimal idea
    contract (no signals = no insight to synthesize)."""
    data = {"updated_at": "2026-05-10T20:19:17-05:00", "run_id": "t-000", "items": []}
    parsed = SubcHandoffInput.model_validate(data)

    with pytest.raises(ValueError, match="no signals|empty"):
        synthesize_idea_contract(
            parsed, chain_id="chain-empty", contract_id="e-01", parent_id=None
        )


# --- RED: tests for the dry-run room builder ---


def test_build_dry_run_room_creates_research_input_and_idea_contract(tmp_path):
    """build_dry_run_room should create a dry-run directory with exactly the
    first two buildroom artifacts and nothing else."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    room_path = build_dry_run_room(parsed, output_dir=str(tmp_path), chain_id="test-chain-1")

    room = Path(room_path)
    assert room.exists()
    assert room.is_dir()

    artifacts = sorted(room.glob("*.json"))
    assert len(artifacts) == 2
    assert artifacts[0].name == "01-research-input.json"
    assert artifacts[1].name == "02-idea-contract.json"

    # Verify both artifacts parse correctly as individual typed Buildroom artifacts
    ri = _load_json(artifacts[0])
    assert ri["artifact_type"] == "research-input"
    assert ri["profile"] == "research"

    ic = _load_json(artifacts[1])
    assert ic["artifact_type"] == "idea-contract"
    assert ic["profile"] == "subc"

    # Parent chain consistency: first has no parent, second links to first
    assert ri["parent_id"] is None
    assert ic["parent_id"] == ri["contract_id"]

    # Ensure it uses the provided chain_id
    assert ri["chain_id"] == "test-chain-1"
    assert ic["chain_id"] == "test-chain-1"


def test_build_dry_run_room_generates_unique_chain_id_per_call(tmp_path):
    """Each call to build_dry_run_room should generate a different chain_id."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    room1 = build_dry_run_room(parsed, output_dir=str(tmp_path), chain_id="chain-a")
    room2 = build_dry_run_room(parsed, output_dir=str(tmp_path), chain_id="chain-b")

    a1 = _load_json(Path(room1) / "01-research-input.json")
    b1 = _load_json(Path(room2) / "01-research-input.json")
    assert a1["chain_id"] != b1["chain_id"]


def test_build_dry_run_room_does_not_create_approval_or_kanban_artifacts(tmp_path):
    """The adapter MUST NOT create intent-review, main-review, Kanban tasks, or
    any artifact beyond research-input and idea-contract."""
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    room_path = build_dry_run_room(parsed, output_dir=str(tmp_path), chain_id="safe-test")

    room = Path(room_path)
    artifact_types = set()
    for path in room.glob("*.json"):
        artifact = _load_json(path)
        artifact_types.add(artifact["artifact_type"])

    forbidden = {"intent-review", "main-review", "product-plan", "build-plan",
                 "verification", "qa-verification", "verification-delta",
                 "trust-report", "retention-review", "operator-summary"}
    assert artifact_types == {"research-input", "idea-contract"}
    assert not (artifact_types & forbidden)


# --- RED: tests for CLI entry point ---


def test_cli_entry_point_help():
    """The CLI entry point should accept --help and exit 0."""
    import subprocess
    import sys

    result = subprocess.run(
        [sys.executable, "-m", "hermes_cli.buildroom.handoff", "--help"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0
    assert "usage" in result.stdout.lower() or "usage" in result.stderr.lower()


def test_cli_entry_point_dry_run(tmp_path):
    """The CLI entry point should create a dry-run room from a fixture handoff."""
    import subprocess
    import sys

    result = subprocess.run(
        [
            sys.executable, "-m", "hermes_cli.buildroom.handoff",
            "--handoff", str(FIXTURE_HANDOFF_PATH),
            "--output", str(tmp_path),
        ],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, f"stderr: {result.stderr}"

    # Should have printed the room path
    output = result.stdout.strip()
    assert len(output) > 0
    room_path = Path(output)
    assert room_path.exists()
    assert (room_path / "01-research-input.json").exists()
    assert (room_path / "02-idea-contract.json").exists()


def test_build_dry_run_room_respects_global_buildroom_lock(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / "buildroom.lock").write_text("stop\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    data = _load_json(FIXTURE_HANDOFF_PATH)
    parsed = SubcHandoffInput.model_validate(data)

    with pytest.raises(RuntimeError, match="Buildroom global lock is active"):
        build_dry_run_room(parsed, output_dir=str(tmp_path / "out"), chain_id="locked")
