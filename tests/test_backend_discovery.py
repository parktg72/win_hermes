"""Phase 2 — multi-backend auto-discovery.

These tests pin the contract that ``hermes`` first-run on Windows can
detect every plausible LLM backend (Anthropic / OpenAI / Codex OAuth /
Gemini / Ollama) and produce a deterministic priority-ordered list.

Each detector is exercised in isolation (env var present / absent,
auth file present / missing / malformed) plus the integrated
``detect_available_backends()`` ordering.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from hermes_cli.backend_discovery import (
    BackendOption,
    _detect_anthropic,
    _detect_codex_oauth,
    _detect_gemini,
    _detect_openai,
    detect_available_backends,
)


# Helpers ─────────────────────────────────────────────────────────────


def _clear_env(monkeypatch):
    for var in (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_TOKEN",
        "CLAUDE_CODE_OAUTH_TOKEN",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)


# ─────────────────────────────────────────────────────────────────────
# Anthropic
# ─────────────────────────────────────────────────────────────────────


def test_anthropic_detected_via_api_key(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-xxxx")
    opt = _detect_anthropic()
    assert isinstance(opt, BackendOption)
    assert opt.id == "anthropic"
    assert "Anthropic" in opt.label


def test_anthropic_detected_via_oauth_token(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "oauth-token-xxx")
    assert _detect_anthropic() is not None


def test_anthropic_not_detected_when_unset(monkeypatch):
    _clear_env(monkeypatch)
    assert _detect_anthropic() is None


# ─────────────────────────────────────────────────────────────────────
# OpenAI
# ─────────────────────────────────────────────────────────────────────


def test_openai_detected_via_api_key(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-xxxx")
    opt = _detect_openai()
    assert isinstance(opt, BackendOption)
    assert opt.id == "openai"


def test_openai_ignores_ollama_sentinel(monkeypatch):
    """Phase-1 sets OPENAI_API_KEY='no-key-required' when routing to Ollama.
    Phase-2 detector must NOT treat that as a real OpenAI backend —
    otherwise Ollama users would falsely see 'OpenAI' in the picker."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "no-key-required")
    assert _detect_openai() is None


def test_openai_not_detected_when_blank(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "")
    assert _detect_openai() is None


# ─────────────────────────────────────────────────────────────────────
# Codex OAuth — ~/.codex/auth.json
# ─────────────────────────────────────────────────────────────────────


def _write_codex_auth(tmp_home: Path, payload: dict | None) -> None:
    codex_dir = tmp_home / ".codex"
    codex_dir.mkdir(parents=True, exist_ok=True)
    auth_file = codex_dir / "auth.json"
    if payload is None:
        # Malformed file
        auth_file.write_text("{ this is not json", encoding="utf-8")
    else:
        auth_file.write_text(json.dumps(payload), encoding="utf-8")


def test_codex_detected_with_valid_tokens(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_codex_auth(
        tmp_path,
        {"tokens": {"access_token": "abc", "refresh_token": "xyz"}},
    )
    opt = _detect_codex_oauth()
    assert opt is not None
    assert opt.id == "openai-codex"


def test_codex_not_detected_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    assert _detect_codex_oauth() is None


def test_codex_not_detected_when_tokens_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_codex_auth(tmp_path, {"tokens": {}})
    assert _detect_codex_oauth() is None


def test_codex_silent_on_malformed_json(tmp_path, monkeypatch):
    """Malformed auth.json must not propagate JSONDecodeError to the picker."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    _write_codex_auth(tmp_path, None)
    assert _detect_codex_oauth() is None


# ─────────────────────────────────────────────────────────────────────
# Gemini — env or oauth file
# ─────────────────────────────────────────────────────────────────────


def test_gemini_detected_via_env(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-xxxx")
    opt = _detect_gemini()
    assert opt is not None
    assert opt.id == "gemini"


def test_gemini_detected_via_google_api_key(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv("GOOGLE_API_KEY", "AIza-xxxx")
    assert _detect_gemini() is not None


def test_gemini_detected_via_oauth_file(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    gem_dir = tmp_path / ".gemini"
    gem_dir.mkdir()
    (gem_dir / "oauth_creds.json").write_text(
        '{"access_token": "ya29.xxxx"}', encoding="utf-8"
    )
    opt = _detect_gemini()
    assert opt is not None
    assert opt.id == "gemini"
    assert "OAuth" in opt.label


def test_gemini_not_detected_with_empty_oauth_file(tmp_path, monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    gem_dir = tmp_path / ".gemini"
    gem_dir.mkdir()
    (gem_dir / "oauth_creds.json").write_text("", encoding="utf-8")
    assert _detect_gemini() is None


# ─────────────────────────────────────────────────────────────────────
# Aggregator — detect_available_backends()
# ─────────────────────────────────────────────────────────────────────


def test_aggregator_returns_empty_when_nothing_configured(tmp_path, monkeypatch):
    """Closed-net Windows PC with no Ollama, no keys → empty list.
    Caller (`_maybe_setup_default_backend`) interprets this as the
    Korean "어느 backend 도 감지되지 않음" guide path."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    # Force Ollama detector to no-op without network calls — replace the
    # registry tuple (patching _detect_ollama doesn't affect the frozen
    # reference already captured in _DETECTORS).
    import hermes_cli.backend_discovery as bd

    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            lambda: None,  # Ollama stubbed out
        ),
    )

    assert detect_available_backends() == []


def test_aggregator_priority_order(tmp_path, monkeypatch):
    """Anthropic < OpenAI < Codex < Gemini < Ollama by detection order
    (= picker display order top-first)."""
    _clear_env(monkeypatch)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-1")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-2")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-3")
    _write_codex_auth(
        tmp_path, {"tokens": {"access_token": "codex-token"}}
    )
    # Stub Ollama as available too — replace the registry tuple so the
    # aggregator picks up the stub (just patching _detect_ollama wouldn't
    # affect the frozen reference inside _DETECTORS).
    import hermes_cli.backend_discovery as bd

    def _stub_ollama():
        return BackendOption(
            id="custom",
            label="Ollama (로컬, 1개 모델)",
            detail="probe ok",
            base_url="http://127.0.0.1:11434/v1",
        )

    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            _stub_ollama,
        ),
    )

    options = detect_available_backends()
    ids = [opt.id for opt in options]
    assert ids == ["anthropic", "openai", "openai-codex", "gemini", "custom"]


def test_aggregator_does_not_write_suggested_model_field(monkeypatch):
    """Phase-2 deliberately drops the `suggested_model` field from
    BackendOption — hardcoding model names goes stale.  This test pins
    that contract so a future "while I'm here" edit doesn't reintroduce it."""
    # Should not be present on the dataclass
    assert "suggested_model" not in BackendOption.__dataclass_fields__


# ─────────────────────────────────────────────────────────────────────
# End-to-end: _maybe_setup_default_backend writes config.yaml
# (advisor-mandated — Phase 1 had this same gap, mirror the fix)
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def isolated_hermes_home(tmp_path, monkeypatch):
    """Wire up Path.home(), HERMES_HOME, and cli._hermes_home so
    save_config_value writes into our tmpdir, not the real ~/.hermes."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    import cli as _cli_mod  # noqa: WPS433

    monkeypatch.setattr(_cli_mod, "_hermes_home", hermes_home, raising=False)
    yield hermes_home


def test_anthropic_env_results_in_config_yaml_provider_anthropic(
    isolated_hermes_home, monkeypatch
):
    """End-to-end: ANTHROPIC_API_KEY set → _maybe_setup_default_backend
    writes config.yaml with model.provider='anthropic' and DOES NOT write
    model.default (per the Phase-2 design — let runtime resolve the
    current flagship)."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-key")

    import hermes_cli.backend_discovery as bd

    # Stub out Ollama to avoid network on systems where it's installed
    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            lambda: None,  # Ollama disabled
        ),
    )

    # Force non-tty so picker auto-picks
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_default_backend()

    import yaml  # type: ignore[import-untyped]

    cfg_path = isolated_hermes_home / "config.yaml"
    assert cfg_path.exists()
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["model"]["provider"] == "anthropic"
    # No model.default — defer to runtime get_default_model_for_provider
    assert "default" not in cfg["model"], (
        f"model.default should NOT be hardcoded: {cfg['model']!r}"
    )


def test_multi_backend_non_tty_auto_picks_top_priority(
    isolated_hermes_home, monkeypatch
):
    """When 2+ backends available and stdin is non-tty (gateway, CI,
    batch run), auto-pick the top-priority backend.  Anthropic > OpenAI
    > Codex > Gemini > Ollama by detection order."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai-real")
    monkeypatch.setenv("GEMINI_API_KEY", "AIza-real")

    import hermes_cli.backend_discovery as bd

    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            lambda: None,
        ),
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_default_backend()

    import yaml  # type: ignore[import-untyped]

    cfg = yaml.safe_load((isolated_hermes_home / "config.yaml").read_text())
    # OpenAI ranks above Gemini → it must win
    assert cfg["model"]["provider"] == "openai"


def test_no_backends_exits_with_korean_guide(
    isolated_hermes_home, monkeypatch, capsys
):
    """0 backends → Korean guide listing all 5 setup options + exit(1)."""
    _clear_env(monkeypatch)

    import hermes_cli.backend_discovery as bd

    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            lambda: None,
        ),
    )

    from hermes_cli import main as main_mod

    with pytest.raises(SystemExit) as exc_info:
        main_mod._maybe_setup_default_backend()
    assert exc_info.value.code == 1

    err = capsys.readouterr().err
    # The 5 listed options must all appear (Korean labels)
    for keyword in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "codex login", "GEMINI_API_KEY", "ollama"):
        assert keyword in err, f"missing setup hint {keyword!r} in: {err!r}"


def test_existing_config_provider_pinned_skips_discovery(
    isolated_hermes_home, monkeypatch
):
    """If user has manually configured ``model.provider`` in config.yaml,
    don't override on subsequent runs — they have made a choice.
    """
    _clear_env(monkeypatch)
    # User has previously pinned anthropic
    cfg_path = isolated_hermes_home / "config.yaml"
    cfg_path.write_text("model:\n  provider: anthropic\n  default: claude-x\n")

    monkeypatch.setenv("OPENAI_API_KEY", "sk-different-provider")

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_default_backend()

    # config.yaml unchanged
    import yaml

    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["model"]["provider"] == "anthropic"
    assert cfg["model"]["default"] == "claude-x"


# ─────────────────────────────────────────────────────────────────────
# Stale-Ollama-pin migration (advisor-mandated narrow fix)
# ─────────────────────────────────────────────────────────────────────


def test_is_stale_ollama_pin_detects_sub_64k_local(monkeypatch):
    """Real user scenario: pre-Phase-1 win_hermes build wrote
    ``gemma2:latest`` to config.yaml, that model has 8K context, and
    the AIAgent would crash at init.  Our detector must say YES."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda name, base_url, api_key="": 8_192,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "gemma2:latest",
            "provider": "custom",
            "base_url": "http://127.0.0.1:11434/v1",
        }
    ) is True


def test_is_stale_ollama_pin_respects_user_context_length_override(monkeypatch):
    """If the user explicitly set ``model.context_length`` in config.yaml,
    they knowingly accepted the small model — don't override."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: 8_192,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "gemma2:latest",
            "provider": "custom",
            "base_url": "http://127.0.0.1:11434/v1",
            "context_length": 8192,  # explicit override
        }
    ) is False


def test_is_stale_ollama_pin_skips_non_custom_provider(monkeypatch):
    """Anthropic / OpenAI / etc. pins must be left alone — even if the
    model name happens to look small or the query function returns 0."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: 100,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "claude-sonnet-4-6",
            "provider": "anthropic",
        }
    ) is False


def test_is_stale_ollama_pin_skips_remote_base_url(monkeypatch):
    """A custom provider pointing at, e.g., a corporate vLLM behind
    https://internal.corp/v1 is not Ollama — don't apply the migration."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: 8_192,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "small-finetune",
            "provider": "custom",
            "base_url": "https://internal.corp/v1",
        }
    ) is False


def test_is_stale_ollama_pin_silent_on_unknown_context(monkeypatch):
    """``query_ollama_num_ctx`` returning None means we couldn't tell —
    err on the side of respecting the existing pin (avoid disruption)."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: None,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "mystery:tag",
            "provider": "custom",
            "base_url": "http://127.0.0.1:11434/v1",
        }
    ) is False


def test_is_stale_ollama_pin_passes_through_64k_models(monkeypatch):
    """A correctly-pinned 128K Ollama model (llama3.1:8b, gemma3:12b)
    must NOT trigger re-run of the picker."""
    from hermes_cli.main import _is_stale_ollama_pin

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: 131_072,
    )
    assert _is_stale_ollama_pin(
        {
            "default": "llama3.1:8b",
            "provider": "custom",
            "base_url": "http://127.0.0.1:11434/v1",
        }
    ) is False


def test_stale_pin_triggers_picker_with_korean_warning(
    isolated_hermes_home, monkeypatch, capsys
):
    """End-to-end: ANTHROPIC_API_KEY set + stale gemma2 pinned in
    config.yaml.  Detector fires → Korean warning to stderr → picker
    runs → config.yaml gets 'anthropic' (or whatever's available)."""
    _clear_env(monkeypatch)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-key")

    cfg_path = isolated_hermes_home / "config.yaml"
    cfg_path.write_text(
        "model:\n"
        "  default: gemma2:latest\n"
        "  provider: custom\n"
        "  base_url: http://127.0.0.1:11434/v1\n"
    )

    monkeypatch.setattr(
        "agent.model_metadata.query_ollama_num_ctx",
        lambda *a, **kw: 8_192,
    )

    import hermes_cli.backend_discovery as bd

    monkeypatch.setattr(
        bd,
        "_DETECTORS",
        (
            bd._detect_anthropic,
            bd._detect_openai,
            bd._detect_codex_oauth,
            bd._detect_gemini,
            lambda: None,
        ),
    )
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_default_backend()

    err = capsys.readouterr().err
    assert "gemma2:latest" in err
    assert "64K" in err

    import yaml

    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["model"]["provider"] == "anthropic", (
        f"stale pin should have been replaced by anthropic: {cfg!r}"
    )



def test_stale_pin_user_actual_scenario_ollama_only(
    isolated_hermes_home, monkeypatch, capsys
):
    """End-to-end mirror of the user's reported state on 2026-05-03:
      - config.yaml: provider=custom, default=gemma2:latest, base_url=localhost
      - Ollama running locally with both gemma2:latest (8K) and gemma3:12b (128K)
      - No Anthropic / OpenAI / Gemini / Codex creds

    After ``_maybe_setup_default_backend()`` returns, the user's stale
    gemma2 pin must be replaced with a 128K model so AIAgent init no
    longer hits the MINIMUM_CONTEXT_LENGTH guard.  The user's "save
    file forever stuck on gemma2" loop is the bug we're closing.
    """
    import sys as _sys
    from unittest.mock import AsyncMock, MagicMock

    _clear_env(monkeypatch)
    cfg_path = isolated_hermes_home / "config.yaml"
    cfg_path.write_text(
        "model:\n"
        "  default: gemma2:latest\n"
        "  provider: custom\n"
        "  base_url: http://127.0.0.1:11434/v1\n"
    )

    # Ollama returns BOTH the stale model and a 128K replacement.
    fake_ollama = MagicMock()
    fake_ollama.fetch_ollama_models = AsyncMock(
        return_value=["gemma2:latest", "gemma3:12b"]
    )
    from hermes_cli.providers.ollama_discovery import (
        OllamaNotRunningError,
        resolve_ollama_base_url,
        select_model as real_select_model,
    )

    fake_ollama.select_model = real_select_model
    fake_ollama.resolve_ollama_base_url = resolve_ollama_base_url
    fake_ollama.OllamaNotRunningError = OllamaNotRunningError
    monkeypatch.setitem(
        _sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_ollama,
    )

    # gemma2 → 8K (stale), gemma3:12b → 128K (compatible)
    def _fake_ctx(name, base_url, api_key=""):
        return {"gemma2:latest": 8_192, "gemma3:12b": 131_072}.get(name)

    monkeypatch.setattr("agent.model_metadata.query_ollama_num_ctx", _fake_ctx)

    # Force non-tty so the picker auto-picks the first compatible model.
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_default_backend()

    # 1. Korean warning printed
    err = capsys.readouterr().err
    assert "gemma2:latest" in err, f"warning missing stale model name: {err!r}"
    assert "한 번만" in err, "Phase-1 promised the warning is one-time"

    # 2. config.yaml's model.default is now the 128K replacement
    import yaml

    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["model"]["default"] == "gemma3:12b", (
        f"stale gemma2 pin not replaced: {cfg['model']!r}"
    )
    assert cfg["model"]["provider"] == "custom"
    assert "127.0.0.1" in cfg["model"]["base_url"]


def test_aggregator_swallows_detector_errors(monkeypatch):
    """A detector that raises must not poison the whole list — Phase-2
    discovery must stay resilient on weird PCs."""

    def _boom():
        raise RuntimeError("simulated PC oddity")

    import hermes_cli.backend_discovery as bd

    monkeypatch.setattr(bd, "_DETECTORS", (_boom, lambda: None))

    # Should return empty list, not raise
    assert detect_available_backends() == []
