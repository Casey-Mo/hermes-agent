"""Operator-facing summaries for sanitized Buildroom rooms."""

from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from .validator import load_validated_artifacts, validate_room


SENSITIVE_MARKERS = ("api_key", "secret", "token", "password", "credential", "bearer", "authorization")
SECRET_VALUE_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9][A-Za-z0-9_-]{12,}"),
    re.compile(r"xai-[A-Za-z0-9_-]{12,}"),
    re.compile(r"AIza[0-9A-Za-z_-]{20,}"),
    re.compile(r"ghp_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]+"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._-]{20,}"),
)


def build_operator_summary(room_path: str | Path) -> dict[str, Any]:
    """Build a compact, sanitized human summary for a Buildroom room.

    The summary intentionally reports counts/states/next actions rather than raw
    evidence text so it can be displayed in dashboards or handoffs without
    leaking secrets from runtime rooms.
    """

    report = validate_room(room_path)
    if not report.valid:
        return {
            "chain_id": report.chain_id,
            "status": "blocked",
            "artifact_count": report.artifact_count,
            "artifact_types": report.artifact_types,
            "errors": report.errors,
            "next_actions": ["repair buildroom artifacts and rerun validator"],
        }

    artifacts = load_validated_artifacts(room_path)
    by_type = {artifact.artifact_type: artifact for artifact in artifacts}
    operator_payload = by_type["operator-summary"].payload
    trust_state = by_type["trust-report"].payload.trust_state
    delta_state = by_type["verification-delta"].payload.delta_state
    retention_state = by_type["retention-review"].payload.retention_state
    verification_status = by_type["verification"].payload.status
    qa_state = by_type["qa-verification"].payload.state

    status = operator_payload.status
    if status == "clean" and (
        verification_status != "passed"
        or qa_state != "passed"
        or delta_state != "none"
        or trust_state != "trusted"
        or retention_state != "retain"
    ):
        status = "needs-review"

    return _sanitize_summary(
        {
            "chain_id": report.chain_id,
            "status": status,
            "artifact_count": report.artifact_count,
            "artifact_types": report.artifact_types,
            "verification_status": verification_status,
            "qa_state": qa_state,
            "delta_state": delta_state,
            "trust_state": trust_state,
            "retention_state": retention_state,
            "summary": operator_payload.summary,
            "next_actions": list(operator_payload.next_actions),
            "rollback_note": operator_payload.rollback_note,
            "evidence_counts": {
                artifact.artifact_type: _payload_evidence_count(artifact.payload)
                for artifact in artifacts
            },
        }
    )


def _payload_evidence_count(payload: Any) -> int:
    evidence = getattr(payload, "evidence", None)
    return len(evidence) if isinstance(evidence, list) else 0


def _sanitize_summary(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_lower = str(key).lower()
            if any(marker in key_lower for marker in SENSITIVE_MARKERS):
                continue
            clean[key] = _sanitize_summary(item)
        return clean
    if isinstance(value, list):
        return [_sanitize_summary(item) for item in value]
    if isinstance(value, str):
        sanitized = value
        for pattern in SECRET_VALUE_PATTERNS:
            sanitized = pattern.sub("[redacted-value]", sanitized)
        for marker in SENSITIVE_MARKERS:
            sanitized = re.sub(re.escape(marker), "[redacted-marker]", sanitized, flags=re.IGNORECASE)
        return sanitized
    return value
