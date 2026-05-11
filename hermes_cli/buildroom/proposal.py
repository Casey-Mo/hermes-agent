"""Hermes Buildroom-to-Kanban proposal engine (dry-run only).

Reads a complete buildroom candidate job (artifacts up through build-plan),
checks approval gates (intent-review, main-review, product-plan), classifies
risk, validates protected surfaces, and produces a dry-run Kanban task graph
as a Python dictionary.

The proposal engine is READ-ONLY: it never creates actual Kanban tasks, never
mutates Hermes config, never touches cron or gateway state. The returned dict
can be serialized to JSON or Markdown for human review.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .safety import buildroom_lock_active, buildroom_lock_path, find_protected_surface_violations
from .validator import load_validated_artifacts, validate_room

# ── Risk band classification ─────────────────────────────────────────────────


RISK_BAND_LABELS: dict[int, str] = {
    0: "documentation",
    1: "additive",
    2: "modified_logic",
    3: "forbidden",
}

DEFAULT_ASSIGNEE_PROFILE = "builder"
ALLOWED_ASSIGNEE_PROFILES = frozenset({
    "builder",
    "opencode-builder",
    "reviewer",
    "analyst",
    "writer",
    "ops",
})


def classify_risk_band(band: int) -> dict[str, Any]:
    """Classify a numeric risk band into a human-readable level.

    Args:
        band: The risk_band from main-review (0-3).

    Returns:
        A dict with band, level, and blocked flag.
    """
    level = RISK_BAND_LABELS.get(band, "unknown")
    return {
        "band": band,
        "level": level,
        "blocked": band == 3 or band not in RISK_BAND_LABELS,
    }


# ── Approval gate checks ─────────────────────────────────────────────────────


def check_approval_gates(room_path: str | Path) -> dict[str, Any]:
    """Check whether a buildroom chain is approved for coder build.

    Required gates:
    1. intent-review decision must be 'approved'
    2. main-review decision must be 'aligned'
    3. product-plan must exist with non-empty allowed_paths
    4. build-plan must exist (coder has a plan to execute)

    Args:
        room_path: Path to a validated buildroom room directory.

    Returns:
        Dict with approved (bool), reason (str), and gates_passed (int).
    """
    report = validate_room(room_path)
    if not report.valid:
        return {
            "approved": False,
            "reason": f"room validation failed: {report.errors[:3]}",
            "gates_passed": 0,
        }

    artifacts = load_validated_artifacts(report.room_path)
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}

    gates_passed = 0
    total_gates = 4

    # Gate 1: intent-review decision == "approved"
    intent = by_type.get("intent-review")
    if intent is None:
        return {"approved": False, "reason": "missing intent-review artifact", "gates_passed": 0}
    if intent.payload.decision != "approved":
        return {
            "approved": False,
            "reason": f"intent-review decision is '{intent.payload.decision}', expected 'approved'",
            "gates_passed": 0,
        }
    gates_passed += 1

    # Gate 2: main-review decision == "aligned"
    main_review = by_type.get("main-review")
    if main_review is None:
        return {"approved": False, "reason": "missing main-review artifact", "gates_passed": gates_passed}
    if main_review.payload.decision != "aligned":
        return {
            "approved": False,
            "reason": f"main-review decision is '{main_review.payload.decision}', expected 'aligned'",
            "gates_passed": gates_passed,
        }
    gates_passed += 1

    # Gate 3: product-plan exists with non-empty allowed_paths
    product_plan = by_type.get("product-plan")
    if product_plan is None:
        return {
            "approved": False,
            "reason": "missing product-plan artifact",
            "gates_passed": gates_passed,
        }
    if not product_plan.payload.allowed_paths:
        return {
            "approved": False,
            "reason": "product-plan.allowed_paths is empty",
            "gates_passed": gates_passed,
        }
    gates_passed += 1

    # Gate 4: build-plan exists
    build_plan = by_type.get("build-plan")
    if build_plan is None:
        return {
            "approved": False,
            "reason": "missing build-plan artifact (coder has no plan)",
            "gates_passed": gates_passed,
        }
    gates_passed += 1

    return {
        "approved": True,
        "reason": "approved_for_coder",
        "gates_passed": gates_passed,
        "total_gates": total_gates,
    }


# ── Protected surface checks ─────────────────────────────────────────────────


def check_protected_surfaces(room_path: str | Path) -> dict[str, Any]:
    """Check whether product-plan.allowed_paths overlaps with protected_surfaces.

    Args:
        room_path: Path to a validated buildroom room directory.

    Returns:
        Dict with clean (bool) and violations (list of dicts).
    """
    report = validate_room(room_path)
    if not report.valid:
        return {"clean": False, "violations": [], "reason": "room validation failed"}

    artifacts = load_validated_artifacts(report.room_path)
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}

    product_plan = by_type.get("product-plan")
    if product_plan is None:
        return {"clean": True, "violations": [], "reason": "no product-plan to check"}

    violations = find_protected_surface_violations(
        product_plan.payload.allowed_paths,
        product_plan.payload.protected_surfaces,
    )

    if violations:
        return {
            "clean": False,
            "violations": [
                {
                    "allowed_path": violation.allowed_path,
                    "protected_surface": violation.protected_surface,
                    "reason": violation.reason,
                }
                for violation in violations
            ],
            "reason": "protected surface violation detected",
        }

    return {"clean": True, "violations": [], "reason": "no violations"}


# ── Task graph builder ───────────────────────────────────────────────────────


def build_task_graph(room_path: str | Path) -> list[dict[str, Any]]:
    """Build a proposed Kanban task graph from the build-plan artifacts.

    Args:
        room_path: Path to a validated buildroom room directory.

    Returns:
        List of task dicts with title, parents, and metadata.
    """
    artifacts = load_validated_artifacts(room_path)
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}

    build_plan = by_type.get("build-plan")
    if build_plan is None:
        return []

    tasks_payload = build_plan.payload.tasks
    if not tasks_payload:
        return []

    task_graph: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    previous_task_id: str | None = None

    for index, task in enumerate(tasks_payload, start=1):
        task_id = _task_id(task, index, seen_ids)
        task_title = str(task.get("description") or task_id)
        parents = _task_parents(task, seen_ids, previous_task_id)
        seen_ids.add(task_id)

        task_graph.append({
            "id": task_id,
            "title": task_title,
            "parents": parents,
            "assignee_profile": _task_assignee_profile(task),
        })
        previous_task_id = task_id

    return task_graph


# ── Idempotency key ──────────────────────────────────────────────────────────



def _task_id(task: dict[str, Any], index: int, seen_ids: set[str]) -> str:
    """Return a unique stable task id for a build-plan task."""

    raw = str(task.get("id") or "").strip()
    base = raw or f"task-{index:03d}"
    if base not in seen_ids:
        return base

    suffix = 2
    while f"{base}-{suffix}" in seen_ids:
        suffix += 1
    return f"{base}-{suffix}"


def _task_parents(
    task: dict[str, Any], seen_ids: set[str], previous_task_id: str | None
) -> list[str]:
    """Return explicit valid parents or a backward-compatible linear parent."""

    explicit = task.get("parents")
    if isinstance(explicit, list):
        parents: list[str] = []
        for parent in explicit:
            parent_id = str(parent).strip()
            if parent_id and parent_id in seen_ids and parent_id not in parents:
                parents.append(parent_id)
        return parents

    if previous_task_id is not None:
        return [previous_task_id]
    return []

def _task_assignee_profile(task: dict[str, Any]) -> str:
    """Return a real Kanban assignee profile for a build-plan task.

    Buildroom artifact profiles intentionally use the abstract role ``coder``.
    Kanban dispatch on Casey's setup uses concrete profiles such as ``builder``
    and ``opencode-builder``. Unknown or missing task routing falls back to the
    conservative default builder lane instead of emitting an unspawnable card.
    """

    requested = str(
        task.get("assignee_profile") or task.get("assignee") or DEFAULT_ASSIGNEE_PROFILE
    )
    if requested in ALLOWED_ASSIGNEE_PROFILES:
        return requested
    return DEFAULT_ASSIGNEE_PROFILE


def _build_idempotency_key(chain_id: str, task_graph: list[dict[str, Any]] | None = None) -> str:
    """Build a deterministic idempotency key from proposal content."""

    payload = {
        "chain_id": chain_id,
        "tasks": [
            {
                "id": task.get("id"),
                "title": task.get("title"),
                "parents": task.get("parents", []),
                "assignee_profile": task.get("assignee_profile"),
            }
            for task in (task_graph or [])
        ],
    }
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    return f"br-proposal-{chain_id}-{digest}"


# ── Full proposal builder ────────────────────────────────────────────────────


def build_dry_run_proposal(room_path: str | Path) -> dict[str, Any]:
    """Build a dry-run Kanban task proposal from a buildroom room.

    This is the main entry point. It:
    1. Validates the room
    2. Checks approval gates
    3. Classifies risk
    4. Checks protected surfaces
    5. Builds task graph from build-plan
    6. Returns a complete proposal dict (does NOT create Kanban tasks)

    Args:
        room_path: Path to a validated buildroom room directory.

    Returns:
        A proposal dict with status, approval, risk, and task_graph.
    """
    room = Path(room_path)
    if buildroom_lock_active():
        return {
            "status": "blocked",
            "approved": False,
            "reason": f"buildroom global lock is active: {buildroom_lock_path()}",
            "source_room": str(room),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    report = validate_room(str(room))

    if not report.valid:
        return {
            "status": "blocked",
            "approved": False,
            "chain_id": report.chain_id,
            "source_room": str(room),
            "errors": report.errors[:5],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Check approval gates
    gates = check_approval_gates(str(room))
    if not gates["approved"]:
        return {
            "status": "blocked",
            "approved": False,
            "reason": gates["reason"],
            "gates_passed": gates["gates_passed"],
            "chain_id": report.chain_id,
            "source_room": str(room),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Get artifacts for data extraction
    artifacts = load_validated_artifacts(str(room))
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}

    main_review = by_type.get("main-review")
    product_plan = by_type.get("product-plan")

    # Extract risk band
    risk_band = main_review.payload.risk_band if main_review else 0
    risk_info = classify_risk_band(risk_band)

    # Reject band 3 (forbidden) early
    if risk_info["blocked"]:
        return {
            "status": "blocked",
            "approved": False,
            "reason": f"risk_band {risk_band} ({risk_info['level']}) is forbidden for autonomous build",
            "chain_id": report.chain_id,
            "source_room": str(room),
            "risk_band": risk_band,
            "risk_level": risk_info["level"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Check protected surfaces
    surface_check = check_protected_surfaces(str(room))
    if not surface_check["clean"]:
        return {
            "status": "blocked",
            "approved": False,
            "reason": "protected surface violation detected",
            "chain_id": report.chain_id,
            "source_room": str(room),
            "risk_band": risk_band,
            "risk_level": risk_info["level"],
            "protected_surface_violations": surface_check["violations"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Build task graph
    task_graph = build_task_graph(str(room))
    if not task_graph:
        return {
            "status": "blocked",
            "approved": False,
            "reason": "no tasks in build-plan",
            "chain_id": report.chain_id,
            "source_room": str(room),
            "risk_band": risk_band,
            "risk_level": risk_info["level"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Extract allowed paths
    allowed_paths = list(product_plan.payload.allowed_paths) if product_plan else []

    # Build idempotency key
    chain_id = report.chain_id or "unknown"
    idempotency_key = _build_idempotency_key(chain_id, task_graph)

    return {
        "status": "dry-run",
        "approved": True,
        "execute": False,
        "chain_id": chain_id,
        "idempotency_key": idempotency_key,
        "source_room": str(room),
        "risk_band": risk_band,
        "risk_level": risk_info["level"],
        "allowed_paths": allowed_paths,
        "task_graph": task_graph,
        "gates_passed": gates["gates_passed"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ── CLI entry point ──────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the proposal engine.

    Usage:
        python -m hermes_cli.buildroom.proposal /path/to/buildroom/room
        python -m hermes_cli.buildroom.proposal /path/to/buildroom/room --format markdown
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate a dry-run Kanban task proposal from a Buildroom room"
    )
    parser.add_argument("room", type=Path, help="Path to a buildroom room directory")
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args(argv)

    result = build_dry_run_proposal(args.room)

    if args.format == "markdown":
        _print_markdown(result)
    else:
        # Strip None keys for clean output
        clean = {k: v for k, v in result.items() if v is not None}
        print(json.dumps(clean, indent=2, default=str))

    return 0 if result.get("approved") or result.get("status") == "dry-run" else 1


def _print_markdown(result: dict[str, Any]) -> None:
    """Print the proposal as a human-readable markdown summary."""
    status = result.get("status", "unknown")
    approved = result.get("approved", False)
    chain_id = result.get("chain_id", "unknown")

    print(f"# Buildroom to Kanban Proposal\n")
    print(f"- **Status**: {status}")
    print(f"- **Chain ID**: {chain_id}")
    print(f"- **Approved**: {approved}")

    if "reason" in result:
        print(f"- **Reason**: {result['reason']}")
    if "risk_band" in result:
        print(f"- **Risk Band**: {result['risk_band']} ({result.get('risk_level', 'unknown')})")
    if "allowed_paths" in result:
        print(f"\n## Allowed Paths\n")
        for path in result["allowed_paths"]:
            print(f"- `{path}`")
    if "task_graph" in result and result["task_graph"]:
        print(f"\n## Task Graph\n")
        for task in result["task_graph"]:
            parents = task.get("parents", [])
            parent_str = f" (after: {', '.join(parents)})" + "" if parents else ""
            print(f"- **{task['title']}**{parent_str}")
    if "errors" in result:
        print(f"\n## Errors\n")
        for error in result["errors"]:
            print(f"- {error}")


if __name__ == "__main__":  # pragma: no cover — exercised by smoke tests
    raise SystemExit(main())
