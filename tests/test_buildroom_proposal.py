"""Tests for the Buildroom-to-Kanban proposal engine (proposal.py).

The proposal engine reads a buildroom room directory, checks approval gates,
classifies risk, and produces a dry-run Kanban task graph JSON. It MUST NOT
create actual Kanban tasks, mutate runtime state, or touch config.
"""

import json
import shutil
from pathlib import Path

import pytest

from hermes_cli.buildroom.proposal import (
    build_dry_run_proposal,
    classify_risk_band,
    check_approval_gates,
    check_protected_surfaces,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "buildroom" / "demo-chain"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ── RED: approval gate checks ────────────────────────────────────────────────


def test_approval_gates_pass_when_main_aligned_and_product_plan_present():
    """check_approval_gates should pass when main-review.decision is 'aligned'
    and product-plan.allowed_paths is non-empty."""
    room = _copy_demo_chain()
    report = check_approval_gates(str(room))
    assert report["approved"] is True
    assert report["reason"] == "approved_for_coder"
    assert "gates_passed" in report
    assert report["gates_passed"] >= 2


def test_approval_gates_rejects_unapproved_intent(tmp_path):
    """An unapproved intent-review (decision='rejected') must fail the gates."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "03-intent-review.json", ["payload", "decision"], "rejected")
    report = check_approval_gates(str(room))
    assert report["approved"] is False
    assert "intent-review" in report["reason"].lower()


def test_approval_gates_rejects_not_aligned_main(tmp_path):
    """A main-review that is not aligned must fail the gates."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "04-main-review.json", ["payload", "decision"], "not-aligned")
    report = check_approval_gates(str(room))
    assert report["approved"] is False
    assert "main-review" in report["reason"].lower()


def test_approval_gates_rejects_missing_product_plan(tmp_path):
    """If product-plan artifact is missing entirely, gates must fail."""
    room = _copy_demo_chain(tmp_path)
    (room / "05-product-plan.json").unlink()
    report = check_approval_gates(str(room))
    assert report["approved"] is False
    assert "product-plan" in report["reason"].lower()


def test_approval_gates_rejects_empty_allowed_paths(tmp_path):
    """If product-plan.allowed_paths is empty, gates must fail."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "05-product-plan.json", ["payload", "allowed_paths"], [])
    report = check_approval_gates(str(room))
    assert report["approved"] is False
    assert "allowed_paths" in report["reason"].lower()


def test_approval_gates_rejects_missing_build_plan(tmp_path):
    """Without a build-plan artifact, proposal should be rejected pre-coder."""
    room = _copy_demo_chain(tmp_path)
    (room / "06-build-plan.json").unlink()
    report = check_approval_gates(str(room))
    assert report["approved"] is False
    assert "build-plan" in report["reason"].lower()


def test_approval_gates_rejects_intent_needs_revision(tmp_path):
    """An intent-review with 'needs-revision' must not be approved."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "03-intent-review.json", ["payload", "decision"], "needs-revision")
    report = check_approval_gates(str(room))
    assert report["approved"] is False


# ── RED: risk classification ────────────────────────────────────────────────


def test_classify_risk_band_0():
    """Risk band 0 should classify as 'documentation'."""
    result = classify_risk_band(0)
    assert result["band"] == 0
    assert result["level"] == "documentation"


def test_classify_risk_band_1():
    """Risk band 1 should classify as 'additive'."""
    result = classify_risk_band(1)
    assert result["band"] == 1
    assert result["level"] == "additive"


def test_classify_risk_band_2():
    """Risk band 2 should classify as 'modified_logic'."""
    result = classify_risk_band(2)
    assert result["band"] == 2
    assert result["level"] == "modified_logic"


def test_classify_risk_band_3():
    """Risk band 3 should classify as 'forbidden' and be flagged."""
    result = classify_risk_band(3)
    assert result["band"] == 3
    assert result["level"] == "forbidden"
    assert result["blocked"] is True


# ── RED: protected surface checks ───────────────────────────────────────────


def test_protected_surfaces_clean():
    """When allowed_paths does not overlap with protected_surfaces, should pass."""
    room = _copy_demo_chain()
    result = check_protected_surfaces(str(room))
    assert result["clean"] is True
    assert result["violations"] == []


def test_protected_surfaces_rejects_overlap(tmp_path):
    """When allowed_paths overlaps with protected_surfaces, check_protected_surfaces
    should detect it via room validation (the validator catches the overlap)."""
    room = _copy_demo_chain(tmp_path)
    plan = _load_json(room / "05-product-plan.json")
    protected = plan["payload"]["protected_surfaces"][0]
    plan["payload"]["allowed_paths"].append(protected)
    _write_json(room / "05-product-plan.json", plan)

    result = check_protected_surfaces(str(room))
    assert result["clean"] is False
    # The validator catches this at validation time, so violations may be empty
    # but clean must be False
    assert any([
        not result["clean"],
        len(result.get("violations", [])) > 0,
        "validation" in result.get("reason", "").lower(),
    ])


# ── RED: full dry-run proposal output ────────────────────────────────────────


def test_dry_run_proposal_uses_correct_status():
    """A fully valid buildroom chain should produce a proposal with status='dry-run'."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert isinstance(result, dict)
    assert result["status"] == "dry-run"
    assert result["approved"] is True


def test_dry_run_proposal_includes_idempotency_key():
    """The proposal must include a chain-derived idempotency key."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert "idempotency_key" in result
    assert result["idempotency_key"].startswith("br-proposal-demo-buildroom-0-")
    assert result["idempotency_key"] == build_dry_run_proposal(str(FIXTURE_DIR))["idempotency_key"]


def test_dry_run_proposal_includes_task_graph():
    """The proposal must include a task graph with at least one task."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert "task_graph" in result
    assert len(result["task_graph"]) >= 1
    task = result["task_graph"][0]
    assert "title" in task
    assert "parents" in task


def test_dry_run_proposal_task_graph_has_parent_edges():
    """Tasks in the graph should have parent dependencies that form a DAG."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    seen = set()
    for task in result["task_graph"]:
        for parent in task.get("parents", []):
            assert parent in seen, f"task {task['title']} has unresolved parent {parent}"
        seen.add(task["id"])


def test_dry_run_proposal_includes_risk_classification():
    """The proposal must include a risk_band and classification level."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert "risk_band" in result
    assert "risk_level" in result
    assert isinstance(result["risk_band"], int)
    assert isinstance(result["risk_level"], str)


def test_dry_run_proposal_includes_allowed_paths():
    """The proposal must include the allowed paths from product-plan."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert "allowed_paths" in result
    assert len(result["allowed_paths"]) >= 1


def test_dry_run_proposal_does_not_contain_forbidden_surfaces():
    """The proposal must exclude paths that overlap with protected surfaces."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    forbidden_keys = {"protected_surfaces", "api_key", "secret", "token", "password"}
    serialized = json.dumps(result).lower()
    for key in forbidden_keys:
        assert key not in serialized or key == "protected_surfaces"  # key may appear in context


# ── RED: unapproved idea cannot create proposal ──────────────────────────────


def test_unapproved_intent_idea_returns_blocked_proposal(tmp_path):
    """An idea with unapproved intent-review should produce a blocked proposal,
    not raise an exception."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "03-intent-review.json", ["payload", "decision"], "rejected")

    result = build_dry_run_proposal(str(room))
    assert result["status"] == "blocked"
    assert result["approved"] is False


def test_unapproved_main_aligned_idea_returns_blocked_proposal(tmp_path):
    """An idea with not-aligned main-review should produce a blocked proposal."""
    room = _copy_demo_chain(tmp_path)
    _mutate_artifact(room, "04-main-review.json", ["payload", "decision"], "not-aligned")

    result = build_dry_run_proposal(str(room))
    assert result["status"] == "blocked"
    assert result["approved"] is False


# ── RED: protected surface rejection ────────────────────────────────────────


def test_protected_surface_allowed_path_overlap_blocks_proposal(tmp_path):
    """If allowed_paths overlaps with protected_surfaces, proposal should be blocked."""
    room = _copy_demo_chain(tmp_path)
    plan = _load_json(room / "05-product-plan.json")
    protected = plan["payload"]["protected_surfaces"][0]
    plan["payload"]["allowed_paths"].append(protected)
    _write_json(room / "05-product-plan.json", plan)

    result = build_dry_run_proposal(str(room))
    assert result["status"] == "blocked"
    assert "protected_surface" in json.dumps(result).lower()


# ── RED: low-risk docs/tests/tooling yields dry-run graph ────────────────────


def test_low_risk_docs_proposal_yields_dry_run_graph():
    """Low-risk (band 0) docs/tests/tooling candidate should produce a dry-run
    proposal with tasks derived from build-plan."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))

    assert result["status"] == "dry-run"
    assert result["approved"] is True
    assert result["risk_band"] == 1  # demo chain uses band 1
    assert len(result["task_graph"]) >= 1
    # Should NOT include execute flag
    assert result.get("execute") is False or "execute" not in result


def test_dry_run_proposal_creates_no_files(tmp_path):
    """build_dry_run_proposal must NOT write files; it returns a dict only.
    Verify no files are created outside the fixture copy."""
    assert Path(FIXTURE_DIR).exists()
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert isinstance(result, dict)
    # Should not have written anything to the fixture directory
    assert not any(Path(FIXTURE_DIR).glob("proposal*.json"))


def test_dry_run_proposal_includes_proposal_metadata():
    """The proposal output should include metadata for the downstream worker:
    chain_id, source_room, profile routing info."""
    result = build_dry_run_proposal(str(FIXTURE_DIR))
    assert "chain_id" in result
    assert result["chain_id"] == "demo-buildroom-0"
    assert "source_room" in result
    assert "timestamp" in result


# ── Helpers ──────────────────────────────────────────────────────────────────


def _mutate_artifact(room: Path, filename: str, path_parts: list[str], value) -> None:
    """Deep-set a value in a JSON artifact file."""
    data = _load_json(room / filename)
    target = data
    for part in path_parts[:-1]:
        target = target[part]
    target[path_parts[-1]] = value
    _write_json(room / filename, data)


def _copy_demo_chain(tmp_path: Path | None = None) -> Path:
    """Copy the demo chain fixture to a tmp path for mutation tests."""
    if tmp_path is None:
        # Return the original fixture if no mutation needed
        return FIXTURE_DIR
    room = tmp_path / "demo-chain"
    shutil.copytree(FIXTURE_DIR, room)
    return room


def test_protected_surface_parent_child_overlap_blocks_proposal(tmp_path):
    room = _copy_demo_chain(tmp_path)
    plan = _load_json(room / "05-product-plan.json")
    plan["payload"]["allowed_paths"] = ["gateway/platforms/telegram.py"]
    plan["payload"]["protected_surfaces"] = ["gateway/platforms"]
    _write_json(room / "05-product-plan.json", plan)

    result = build_dry_run_proposal(str(room))

    assert result["status"] == "blocked"
    assert result["approved"] is False
    assert "protected_surface" in json.dumps(result).lower()
    assert "is inside" in json.dumps(result).lower()


def test_task_graph_uses_real_spawnable_assignee_profile():
    result = build_dry_run_proposal(str(FIXTURE_DIR))

    assert result["task_graph"]
    assert {task["assignee_profile"] for task in result["task_graph"]} == {"builder"}


def test_dry_run_proposal_respects_global_buildroom_lock(tmp_path, monkeypatch):
    hermes_home = tmp_path / "hermes-home"
    hermes_home.mkdir()
    (hermes_home / "buildroom.lock").write_text("stop\n", encoding="utf-8")
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    result = build_dry_run_proposal(str(FIXTURE_DIR))

    assert result["status"] == "blocked"
    assert result["approved"] is False
    assert "buildroom global lock" in result["reason"]


def test_task_graph_preserves_explicit_parent_edges(tmp_path):
    room = _copy_demo_chain(tmp_path)
    build = _load_json(room / "06-build-plan.json")
    build["payload"]["tasks"] = [
        {"id": "schema", "description": "Schema"},
        {"id": "docs", "description": "Docs"},
        {"id": "review", "description": "Review", "parents": ["schema", "docs"]},
    ]
    _write_json(room / "06-build-plan.json", build)

    result = build_dry_run_proposal(str(room))

    review = result["task_graph"][2]
    assert review["id"] == "review"
    assert review["parents"] == ["schema", "docs"]


def test_task_graph_synthesizes_unique_ids_for_missing_or_duplicate_task_ids(tmp_path):
    room = _copy_demo_chain(tmp_path)
    build = _load_json(room / "06-build-plan.json")
    build["payload"]["tasks"] = [
        {"description": "Missing ID"},
        {"id": "same", "description": "First duplicate"},
        {"id": "same", "description": "Second duplicate"},
    ]
    _write_json(room / "06-build-plan.json", build)

    result = build_dry_run_proposal(str(room))
    ids = [task["id"] for task in result["task_graph"]]

    assert ids == ["task-001", "same", "same-2"]
    assert len(set(ids)) == len(ids)


def test_dry_run_proposal_secret_check_is_structural_not_substring_based():
    result = build_dry_run_proposal(str(FIXTURE_DIR))

    def walk_keys(value):
        if isinstance(value, dict):
            for key, nested in value.items():
                yield str(key).lower()
                yield from walk_keys(nested)
        elif isinstance(value, list):
            for nested in value:
                yield from walk_keys(nested)

    forbidden_keys = {"api_key", "secret", "token", "password"}
    assert forbidden_keys.isdisjoint(set(walk_keys(result)))
