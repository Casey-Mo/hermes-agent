"""Hermes Research→Subc handoff adapter for the Buildroom.

Reads a sanitized subc-handoff.json (shaped like the research profile's queue
item) and produces a dry-run Buildroom room with the first two contract
artifacts only: research-input and idea-contract.

No approvals, Kanban tasks, cron jobs, or runtime config mutations — this is a
pure dry-run, proposal-first adapter.

v1 is manual/proposal-first only. A future adapter may pass the idea-contract
to an intent-review step, but v1 never approves anything automatically.

Safe for no-agent cron dry-run: has no side effects beyond writing JSON files
to a designated dry-run directory and printing the path to stdout.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .schemas import (
    IdeaContractPayload,
    ResearchInputPayload,
    ResearchInputArtifact,
    IdeaContractArtifact,
)

# ── Input model for subc-handoff.json ───────────────────────────────────────


class HandoffItem(BaseModel):
    """One signal item from the research profile's subc-handoff queue."""

    model_config = ConfigDict(extra="forbid")

    topic: str
    signal: str
    confidence: str | None = None
    suggested_walk_mode: str | None = None


class SubcHandoffInput(BaseModel):
    """Sanitized research profile subc-handoff.json shape.

    Extra fields are forbidden so real profile state (secrets, tokens, runtime
    data) does not leak into fixture-based or dry-run processing.
    """

    model_config = ConfigDict(extra="forbid")

    updated_at: str | None = None
    run_id: str | None = None
    items: list[HandoffItem] = []


# ── Helpers ─────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── Research-input builder ──────────────────────────────────────────────────


DEFAULT_CONSTRAINTS: tuple[str, ...] = (
    "dry-run/manual v1 only — no auto-approval or automatic execution",
    "adapter does not create Kanban tasks, cron jobs, or mutate Hermes config",
    "adapter does not edit HTC or other product repositories",
)


class ResearchInputBuilder:
    """Deterministic builder for ResearchInputPayload from subc-handoff data."""

    @classmethod
    def build(
        cls,
        handoff: SubcHandoffInput,
        chain_id: str,
        contract_id: str,
    ) -> ResearchInputPayload:
        """Convert a subc handoff into a research-input payload.

        Arguments:
            handoff: Parsed subc-handoff data.
            chain_id: Buildroom chain identifier.
            contract_id: Unique contract identifier for this artifact.

        Returns:
            A validated ResearchInputPayload.
        """
        topics = cls._collect_topics(handoff)
        signals = cls._collect_signals(handoff)
        evidence = cls._collect_evidence(handoff)

        title = f"Research handoff from subc run {handoff.run_id or 'unknown'}"

        return ResearchInputPayload(
            title=title,
            signals=signals,
            evidence=evidence,
            constraints=list(DEFAULT_CONSTRAINTS),
        )

    @staticmethod
    def _collect_topics(handoff: SubcHandoffInput) -> list[str]:
        topics = sorted({item.topic for item in handoff.items if item.topic})
        return topics if topics else ["no-subc-signals"]

    @staticmethod
    def _collect_signals(handoff: SubcHandoffInput) -> list[str]:
        if not handoff.items:
            return ["no-subc-signals"]
        return [
            f"{item.topic}: {item.signal[:200]}"
            for item in handoff.items
            if item.signal
        ]

    @staticmethod
    def _collect_evidence(handoff: SubcHandoffInput) -> list[str]:
        if not handoff.items:
            return ["no-subc-signals"]
        lines: list[str] = []
        for item in handoff.items:
            if item.signal:
                lines.append(f"[{item.topic}] {item.signal[:240]}")
        return lines


# ── Idea-contract synthesizer ───────────────────────────────────────────────


def synthesize_idea_contract(
    handoff: SubcHandoffInput,
    chain_id: str,
    contract_id: str,
    parent_id: str | None = None,
    research_refs: list[str] | None = None,
) -> IdeaContractPayload:
    """Synthesize an idea-contract payload from the subc handoff signals.

    Raises ValueError if the handoff contains no signals to synthesize from.
    """
    if not handoff.items:
        raise ValueError("cannot synthesize idea-contract from empty subc handoff (no signals)")

    topics = ResearchInputBuilder._collect_topics(handoff)

    title = f"Build from subc handoff: {', '.join(topics[:3])}"
    if len(topics) > 3:
        title += f" (+{len(topics) - 3} more)"

    problem_statement = (
        f"Subc/Dreamer has observed {len(handoff.items)} signal(s) across "
        f"{len(topics)} topic(s): {', '.join(topics[:5])}"
        + (f" and {len(topics) - 5} more" if len(topics) > 5 else "")
        + ". These signals may indicate work worth pursuing but require main-approval before any build."
    )

    proposed_solution = (
        "Route through main-review for intent check and alignment. "
        "If approved, the analyst produces a bounded product-plan, then coder "
        "builds, QA verifies independently, trust reports on quality, and "
        "retention reviews the outcome."
    )

    estimated_impact = (
        f"Proposal derived from {len(handoff.items)} subc signal(s) "
        f"(confidence: {_confidence_summary(handoff)}). "
        "Full impact assessment deferred to main-review and product-plan stages."
    )

    refs = research_refs or []
    if handoff.run_id:
        refs.append(f"run/{handoff.run_id}")

    return IdeaContractPayload(
        title=title,
        problem_statement=problem_statement,
        proposed_solution=proposed_solution,
        research_refs=refs if refs else ["no-handoff-refs"],
        estimated_impact=estimated_impact,
    )




def _confidence_summary(handoff: SubcHandoffInput) -> str:
    """Build a confidence summary string from the handoff's items."""
    counts: dict[str, int] = {}
    for item in handoff.items:
        c = item.confidence or "unknown"
        counts[c] = counts.get(c, 0) + 1
    if not counts:
        return "none"
    parts = [f"{k}={v}" for k, v in sorted(counts.items())]
    return "; ".join(parts)


# ── Dry-run room builder ────────────────────────────────────────────────────


def build_dry_run_room(
    handoff: SubcHandoffInput,
    output_dir: str = ".",
    chain_id: str | None = None,
) -> str:
    """Create a dry-run Buildroom room directory from a subc handoff.

    Writes exactly two artifacts:
        01-research-input.json
        02-idea-contract.json

    Args:
        handoff: Parsed subc-handoff data.
        output_dir: Directory under which to create the room (default: cwd).
        chain_id: Explicit chain id. If None, auto-generates one.

    Returns:
        Absolute path to the created room directory.
    """
    if chain_id is None:
        ts = datetime.now(timezone.utc).strftime("br-%Y%m%d-%H%M%S")
        chain_id = f"{ts}-{_hex_suffix()}"

    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)

    # Room name derived from chain_id for determinism
    room_name = f"dry-run-{chain_id}"
    room_path = output / room_name
    room_path.mkdir(parents=True, exist_ok=True)

    contract_id_01 = f"{chain_id}-01"
    contract_id_02 = f"{chain_id}-02"

    # Build research input
    research_payload = ResearchInputBuilder.build(handoff, chain_id, contract_id_01)
    research_artifact = ResearchInputArtifact(
        contract_id=contract_id_01,
        parent_id=None,
        chain_id=chain_id,
        artifact_type="research-input",
        version="1.0.0",
        timestamp=_now_iso(),
        profile="research",
        payload=research_payload,
    )

    # Build idea contract
    idea_payload = synthesize_idea_contract(
        handoff,
        chain_id=chain_id,
        contract_id=contract_id_02,
        parent_id=contract_id_01,
        research_refs=[contract_id_01],
    )
    idea_artifact = IdeaContractArtifact(
        contract_id=contract_id_02,
        parent_id=contract_id_01,
        chain_id=chain_id,
        artifact_type="idea-contract",
        version="1.0.0",
        timestamp=_now_iso(),
        profile="subc",
        payload=idea_payload,
    )

    _write_artifact(room_path / "01-research-input.json", research_artifact)
    _write_artifact(room_path / "02-idea-contract.json", idea_artifact)

    return str(room_path)


def _hex_suffix(length: int = 6) -> str:
    """Generate a small random hex suffix for chain id uniqueness."""
    import secrets

    return secrets.token_hex(length // 2 + 1)[:length]


def _write_artifact(path: Path, artifact: ResearchInputArtifact | IdeaContractArtifact) -> None:
    """Serialize a Buildroom artifact to JSON, using model_dump for Pydantic v2."""
    data = artifact.model_dump(mode="json")
    # Convert datetime to ISO string for clean JSON
    if "timestamp" in data and hasattr(data["timestamp"], "isoformat"):
        data["timestamp"] = data["timestamp"].isoformat()
    path.write_text(json.dumps(data, indent=2, default=str) + "\n", encoding="utf-8")


# ── CLI entry point ─────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> int:
    """CLI entry point for the handoff adapter.

    Usage:
        python -m hermes_cli.buildroom.handoff \\
            --handoff /path/to/subc-handoff.json \\
            --output /path/to/dry-run/dir
    """
    parser = argparse.ArgumentParser(
        description="Convert a research profile subc-handoff.json into a dry-run Buildroom room"
    )
    parser.add_argument(
        "--handoff",
        type=Path,
        required=True,
        help="Path to subc-handoff.json from the research profile's queue",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("."),
        help="Output directory for the dry-run Buildroom room (default: cwd)",
    )
    parser.add_argument(
        "--chain-id",
        type=str,
        default=None,
        help="Explicit chain id (default: auto-generated)",
    )
    args = parser.parse_args(argv)

    handoff_path = args.handoff.resolve()
    if not handoff_path.exists():
        print(f"ERROR: handoff file not found: {handoff_path}", file=__import__("sys").stderr)
        return 1

    raw = json.loads(handoff_path.read_text(encoding="utf-8"))
    handoff = SubcHandoffInput.model_validate(raw)

    room_path = build_dry_run_room(
        handoff,
        output_dir=str(args.output.resolve()),
        chain_id=args.chain_id,
    )

    print(room_path)
    return 0


if __name__ == "__main__":  # pragma: no cover — exercised by smoke tests
    raise SystemExit(main())
