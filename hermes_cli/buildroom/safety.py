"""Safety primitives shared by Buildroom adapters.

Buildroom code is intentionally proposal-first. These helpers centralize the
small amount of runtime safety logic that adapters need before they read or
write dry-run artifacts.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_LOCK_FILE_NAME = "buildroom.lock"


@dataclass(frozen=True, slots=True)
class ProtectedSurfaceViolation:
    """A normalized allowed/protected path containment violation."""

    allowed_path: str
    protected_surface: str
    reason: str

    def format(self) -> str:
        return (
            f"allowed_path {self.allowed_path!r} {self.reason} "
            f"protected_surface {self.protected_surface!r}"
        )


def hermes_home() -> Path:
    """Return the active Hermes home for Buildroom runtime controls."""

    return Path(os.environ.get("HERMES_HOME", Path.home() / ".hermes")).expanduser()


def buildroom_lock_path() -> Path:
    """Return the global Buildroom lock-file path."""

    return hermes_home() / _LOCK_FILE_NAME


def buildroom_lock_active() -> bool:
    """Whether the operator has enabled the global Buildroom stop file."""

    return buildroom_lock_path().exists()


def assert_buildroom_unlocked() -> None:
    """Raise if the operator stop file is present.

    The exception message intentionally includes the exact lock-file path so the
    operator can inspect/remove it, but never includes environment values or
    secrets.
    """

    lock = buildroom_lock_path()
    if lock.exists():
        raise RuntimeError(f"Buildroom global lock is active: {lock}")


def find_protected_surface_violations(
    allowed_paths: Iterable[str], protected_surfaces: Iterable[str]
) -> list[ProtectedSurfaceViolation]:
    """Find exact and containment overlap between allowed paths and protected surfaces.

    A Buildroom plan is unsafe when an allowed path equals a protected surface,
    when an allowed directory is a parent of a protected child, or when an
    allowed child sits inside a protected parent. Paths are compared after
    ``~`` expansion, lexical normalization, and trailing-slash normalization.
    Relative paths are compared only with relative paths; absolute paths only
    with absolute paths, except exact raw-string matches are still caught.
    """

    allowed = [
        (raw, normalized)
        for raw in allowed_paths
        if (normalized := _normalize_policy_path(raw)) is not None
    ]
    protected = [
        (raw, normalized)
        for raw in protected_surfaces
        if (normalized := _normalize_policy_path(raw)) is not None
    ]

    violations: list[ProtectedSurfaceViolation] = []
    seen: set[tuple[str, str, str]] = set()
    for allowed_raw, allowed_norm in allowed:
        for protected_raw, protected_norm in protected:
            reason = _overlap_reason(allowed_norm, protected_norm)
            if reason is None:
                continue
            key = (allowed_raw, protected_raw, reason)
            if key in seen:
                continue
            seen.add(key)
            violations.append(
                ProtectedSurfaceViolation(
                    allowed_path=allowed_raw,
                    protected_surface=protected_raw,
                    reason=reason,
                )
            )
    return violations


def _normalize_policy_path(value: str) -> Path | None:
    """Normalize a path-like policy string without requiring it to exist."""

    text = str(value).strip()
    if not text:
        return None
    expanded = os.path.expanduser(text)
    normalized = os.path.normpath(expanded)
    return Path(normalized)


def _overlap_reason(allowed: Path, protected: Path) -> str | None:
    """Return a human-readable overlap reason, or None if paths are disjoint."""

    if allowed == protected:
        return "equals"

    # Avoid treating an absolute path as a child of a relative policy token, or
    # vice versa. That would make labels like "gateway/platform config" behave
    # like filesystem grants in unrelated workspaces.
    if allowed.is_absolute() != protected.is_absolute():
        return None

    if _is_relative_to(protected, allowed):
        return "contains"
    if _is_relative_to(allowed, protected):
        return "is inside"
    return None


def _is_relative_to(candidate: Path, parent: Path) -> bool:
    """Version-compatible ``Path.is_relative_to`` wrapper, excluding equality."""

    if candidate == parent:
        return False
    try:
        candidate.relative_to(parent)
    except ValueError:
        return False
    return True
