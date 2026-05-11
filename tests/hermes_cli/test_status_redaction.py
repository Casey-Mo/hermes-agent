from types import SimpleNamespace

from hermes_cli import status


def test_status_all_redacts_api_key_values(monkeypatch, tmp_path, capsys):
    """`hermes status --all` is documented as shareable, so it must not leak secrets."""
    secret = "xai-THIS_IS_A_SECRET_STATUS_REDACTION_SHOULD_HIDE_1234567890ABCDE"

    def fake_get_env_value(name):
        if name == "XAI_API_KEY":
            return secret
        return ""

    monkeypatch.setattr(status, "get_env_value", fake_get_env_value)
    monkeypatch.setattr(status, "get_env_path", lambda: tmp_path / ".env")
    monkeypatch.setattr(status, "get_hermes_home", lambda: tmp_path)
    monkeypatch.setattr(status, "load_config", lambda: {"model": {"default": "test-model", "provider": "test"}})
    monkeypatch.setattr(status, "_effective_provider_label", lambda: "Test Provider")
    monkeypatch.setattr(status, "managed_nous_tools_enabled", lambda: False)

    status.show_status(SimpleNamespace(all=True, deep=False))

    output = capsys.readouterr().out
    assert secret not in output
    assert "xai-" in output
    assert "THIS_IS_A_SECRET" not in output
