"""Unit tests for Buildroom safety primitives."""

from hermes_cli.buildroom.safety import find_protected_surface_violations


def test_protected_surface_helper_detects_tilde_expanded_exact_match(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    violations = find_protected_surface_violations(
        ["~/.hermes/.env"],
        [str(home / ".hermes" / ".env")],
    )

    assert len(violations) == 1
    assert violations[0].reason == "equals"


def test_protected_surface_helper_normalizes_dot_dot_and_trailing_slashes():
    violations = find_protected_surface_violations(
        ["hermes_cli/buildroom/../config/"],
        ["hermes_cli/config/providers.py"],
    )

    assert len(violations) == 1
    assert violations[0].reason == "contains"


def test_protected_surface_helper_does_not_compare_absolute_to_relative():
    violations = find_protected_surface_violations(
        ["/tmp/hermes_cli"],
        ["hermes_cli"],
    )

    assert violations == []


def test_protected_surface_helper_ignores_blank_policy_entries():
    violations = find_protected_surface_violations(
        ["hermes_cli/buildroom", "  "],
        ["", "hermes_cli/buildroom/proposal.py"],
    )

    assert len(violations) == 1
    assert violations[0].protected_surface == "hermes_cli/buildroom/proposal.py"
