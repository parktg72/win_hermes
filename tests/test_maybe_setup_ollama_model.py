"""Integration tests for hermes_cli.main._maybe_setup_ollama_model.

Covers the full chain that runs at the start of `hermes chat`:
  config.json read → fetch_ollama_models → select_model → persist + env set,
  with the Korean error path on Ollama-not-running.
"""
import json
import os
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def test_skips_when_hermes_model_already_set(monkeypatch):
    monkeypatch.setenv("HERMES_MODEL", "ollama/preset")
    from hermes_cli.main import _maybe_setup_ollama_model

    mock_fetch = AsyncMock()
    with patch(
        "hermes_cli.providers.ollama_discovery.fetch_ollama_models",
        new=mock_fetch,
    ):
        _maybe_setup_ollama_model()

    mock_fetch.assert_not_called()


def test_exits_with_korean_stderr_when_ollama_not_running(
    monkeypatch, tmp_path, capsys
):
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from hermes_cli.main import _maybe_setup_ollama_model
    from hermes_cli.providers.ollama_discovery import OllamaNotRunningError

    msg = "Ollama가 실행되지 않았습니다. `ollama serve` 실행 후 재시작하세요."
    mock_fetch = AsyncMock(side_effect=OllamaNotRunningError(msg))
    with patch(
        "hermes_cli.providers.ollama_discovery.fetch_ollama_models",
        new=mock_fetch,
    ):
        with pytest.raises(SystemExit) as excinfo:
            _maybe_setup_ollama_model()
        assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "Ollama" in captured.err
    assert "ollama serve" in captured.err
    assert any("가" <= ch <= "힣" for ch in captured.err), "expected Korean"


def test_persists_first_model_when_no_saved(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from hermes_cli.main import _maybe_setup_ollama_model

    mock_fetch = AsyncMock(return_value=["llama3.2:latest", "mistral:7b"])
    with patch(
        "hermes_cli.providers.ollama_discovery.fetch_ollama_models",
        new=mock_fetch,
    ):
        _maybe_setup_ollama_model()

    config = tmp_path / ".hermes" / "config.json"
    assert config.exists(), "config.json not written"
    saved = json.loads(config.read_text(encoding="utf-8"))
    assert saved["ollama_model"] == "llama3.2:latest"
    assert os.environ.get("HERMES_MODEL") == "ollama/llama3.2:latest"


def test_uses_saved_model_when_still_available(monkeypatch, tmp_path):
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg_dir = tmp_path / ".hermes"
    cfg_dir.mkdir()
    (cfg_dir / "config.json").write_text(
        json.dumps({"ollama_model": "mistral:7b"}), encoding="utf-8"
    )

    from hermes_cli.main import _maybe_setup_ollama_model

    mock_fetch = AsyncMock(return_value=["llama3.2:latest", "mistral:7b"])
    with patch(
        "hermes_cli.providers.ollama_discovery.fetch_ollama_models",
        new=mock_fetch,
    ):
        _maybe_setup_ollama_model()

    assert os.environ.get("HERMES_MODEL") == "ollama/mistral:7b"


def test_exits_with_korean_stderr_when_no_models(monkeypatch, tmp_path, capsys):
    """Ollama is up but has zero models → Korean guidance + exit(1)."""
    monkeypatch.delenv("HERMES_MODEL", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    from hermes_cli.main import _maybe_setup_ollama_model

    mock_fetch = AsyncMock(return_value=[])
    with patch(
        "hermes_cli.providers.ollama_discovery.fetch_ollama_models",
        new=mock_fetch,
    ):
        with pytest.raises(SystemExit) as excinfo:
            _maybe_setup_ollama_model()
        assert excinfo.value.code == 1

    captured = capsys.readouterr()
    assert "ollama pull" in captured.err
    assert any("가" <= ch <= "힣" for ch in captured.err), "expected Korean"
