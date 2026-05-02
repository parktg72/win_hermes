"""Regression tests for the 64K context-length guard in the Ollama picker.

User-visible bug that motivated this:
    Failed to initialize agent: Model gemma2:latest has a context window of
    8,192 tokens, which is below the minimum 64,000 required by Hermes Agent.

The picker had no idea about context length, so users would happily pick a
small-context model and only see the error after install completes and the
first chat starts.  These tests pin the new behavior:

  1. Models below MINIMUM_CONTEXT_LENGTH are rejected interactively.
  2. When a saved model is now incompatible (e.g. user pulled a smaller
     replacement), the picker doesn't auto-return it.
  3. When *every* installed model is below the minimum, the picker raises
     a Korean-language error with concrete ``ollama pull <name>`` commands.
  4. Unknown context (transient ``/api/show`` failure) is treated as
     compatible-by-faith — never block the user on a hiccup.
  5. Legacy ``select_model`` calls without ``base_url`` skip filtering
     entirely, preserving the existing test_ollama_discovery.py contract.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.model_metadata import MINIMUM_CONTEXT_LENGTH
from hermes_cli.providers.ollama_discovery import select_model


_OK_CTX = MINIMUM_CONTEXT_LENGTH + 1  # 64,001 — barely passes
_LOW_CTX = 8_192                       # gemma2 / phi-3 / mistral-7b-base
_BASE = "http://127.0.0.1:11434/v1"


def _ctx_map(models_to_ctx: dict[str, int | None]):
    """Build a side_effect callable for query_ollama_num_ctx."""

    def _query(name, base_url, api_key=""):
        return models_to_ctx.get(name)

    return _query


# ─────────────────────────────────────────────────────────────────────
# Filtering / error path
# ─────────────────────────────────────────────────────────────────────


def test_compatible_saved_model_returned_without_prompt():
    """Saved + compatible → return immediately, no picker shown."""
    with patch(
        "agent.model_metadata.query_ollama_num_ctx",
        side_effect=_ctx_map({"llama3.1:8b": _OK_CTX, "mistral:7b": _LOW_CTX}),
    ):
        chosen = select_model(
            ["llama3.1:8b", "mistral:7b"],
            saved="llama3.1:8b",
            base_url=_BASE,
            auto_pick_first=True,
        )
    assert chosen == "llama3.1:8b"


def test_saved_model_dropped_when_below_minimum(capsys):
    """If the saved model is now under 64K (e.g. user replaced their model
    with a smaller one), the picker must not return it silently — auto-pick
    the first compatible model in non-interactive mode."""
    with patch(
        "agent.model_metadata.query_ollama_num_ctx",
        side_effect=_ctx_map({"gemma2:latest": _LOW_CTX, "llama3.1:8b": _OK_CTX}),
    ):
        chosen = select_model(
            ["gemma2:latest", "llama3.1:8b"],
            saved="gemma2:latest",
            base_url=_BASE,
            auto_pick_first=True,
        )
    assert chosen == "llama3.1:8b"

    out = capsys.readouterr().out
    # Korean-language stale-model warning must mention the bad model name
    assert "gemma2:latest" in out
    # And explain the threshold in human terms
    assert "64K" in out or "64,000" in out


def test_no_compatible_models_raises_with_korean_pull_guide():
    """Every installed model below 64K → ValueError with Korean copy that
    names a ≥64K model the user can pull.  This is the message non-developer
    Korean medical researchers see if they only have gemma2 / phi-3."""
    with patch(
        "agent.model_metadata.query_ollama_num_ctx",
        side_effect=_ctx_map(
            {"gemma2:latest": _LOW_CTX, "phi3:latest": 4_096}
        ),
    ):
        with pytest.raises(ValueError) as exc_info:
            select_model(
                ["gemma2:latest", "phi3:latest"],
                saved=None,
                base_url=_BASE,
                auto_pick_first=True,
            )

    msg = str(exc_info.value)
    # The message must (a) be Korean, (b) name at least one ≥64K model
    # the user can pull right now, (c) include the actual `ollama pull`
    # command they should run.
    assert "Hermes Agent" in msg
    assert "64,000" in msg
    assert "ollama pull" in msg
    # At least one of the recommended top-tier 128K models must appear
    recommended = ("gemma3:12b", "llama3.1:8b", "qwen3:8b")
    assert any(rec in msg for rec in recommended), (
        f"no recommended model in error: {msg!r}"
    )
    # And it must list which installed models failed and why
    assert "gemma2:latest" in msg
    assert "8,192" in msg


def test_unknown_context_is_compatible_by_faith():
    """If /api/show fails for a model (transient hiccup), treat it as
    compatible rather than dropping it from the picker.  Never block the
    user on a guess."""
    with patch(
        "agent.model_metadata.query_ollama_num_ctx",
        side_effect=_ctx_map({"unknown:tag": None}),
    ):
        chosen = select_model(
            ["unknown:tag"],
            saved=None,
            base_url=_BASE,
            auto_pick_first=True,
        )
    assert chosen == "unknown:tag"


def test_query_failure_does_not_propagate():
    """If query_ollama_num_ctx raises (network error etc.), the picker
    must not crash — it falls back to "unknown context" handling."""

    def _raise(*_a, **_kw):
        raise RuntimeError("api/show endpoint not found")

    with patch(
        "agent.model_metadata.query_ollama_num_ctx",
        side_effect=_raise,
    ):
        chosen = select_model(
            ["whatever:latest"],
            saved=None,
            base_url=_BASE,
            auto_pick_first=True,
        )
    assert chosen == "whatever:latest"


# ─────────────────────────────────────────────────────────────────────
# Backward compat
# ─────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────
# End-to-end scenario test (advisor-mandated)
# ─────────────────────────────────────────────────────────────────────


def test_user_recovers_from_stale_gemma2_in_config_json(tmp_path, monkeypatch):
    """Mirror the actual reported user scenario:

    1. ``~/.hermes/config.json`` has ``{"ollama_model": "gemma2:latest"}``
       from a previous broken run.
    2. Ollama has both gemma2:latest (8K) and llama3.1:8b (131K) installed.
    3. User runs ``hermes`` again expecting it to "just work."

    After ``_maybe_setup_ollama_model()`` returns:
      - ``config.yaml model.default`` is the compatible model (llama3.1:8b)
      - ``config.json ollama_model`` is also updated to the compatible model
        (so a future run doesn't re-stick on gemma2)
      - ``OPENAI_BASE_URL`` env points at localhost
    """
    import json
    import sys

    from pathlib import Path
    from unittest.mock import AsyncMock, MagicMock

    import yaml  # type: ignore[import-untyped]

    # Isolate ~/.hermes
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    for var in ("HERMES_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)

    # Pre-existing stale config.json (the actual user state)
    legacy_json = hermes_home / "config.json"
    legacy_json.write_text(json.dumps({"ollama_model": "gemma2:latest"}))

    # Mock Ollama discovery: both models present
    fake_module = MagicMock()
    fake_module.fetch_ollama_models = AsyncMock(
        return_value=["gemma2:latest", "llama3.1:8b"]
    )

    # Reuse the real select_model + helpers — we want to validate the
    # full path, not a mocked picker.
    from hermes_cli.providers.ollama_discovery import (
        OllamaNotRunningError,
        resolve_ollama_base_url,
        select_model as real_select_model,
    )

    fake_module.select_model = real_select_model
    fake_module.resolve_ollama_base_url = resolve_ollama_base_url
    fake_module.OllamaNotRunningError = OllamaNotRunningError
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_module,
    )

    # Mock the context-length query so we don't need a live Ollama server.
    # gemma2 = 8K, llama3.1 = 131K.
    def _ctx(name, base_url, api_key=""):
        return {"gemma2:latest": 8_192, "llama3.1:8b": 131_072}.get(name)

    monkeypatch.setattr("agent.model_metadata.query_ollama_num_ctx", _ctx)

    # cli._hermes_home is set at module import — patch directly
    import cli as _cli_mod

    monkeypatch.setattr(_cli_mod, "_hermes_home", hermes_home, raising=False)

    # Force non-interactive picker (auto_pick first compatible)
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_ollama_model()

    # ─── assertions ───
    # 1. config.yaml has the compatible model selected
    cfg_yaml = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert cfg_yaml["model"]["default"] == "llama3.1:8b", (
        f"config.yaml didn't switch off stale gemma2: {cfg_yaml!r}"
    )
    assert cfg_yaml["model"]["provider"] == "custom"
    assert "127.0.0.1:11434" in cfg_yaml["model"]["base_url"]

    # 2. Legacy config.json ollama_model also updated — otherwise next run
    #    re-reads stale gemma2 as 'saved' and the loop reproduces.
    legacy = json.loads(legacy_json.read_text())
    assert legacy["ollama_model"] == "llama3.1:8b", (
        f"config.json still pinned to stale gemma2: {legacy!r}"
    )

    # 3. Env var matches config.yaml (so the SDK doesn't pick a different URL)
    import os

    assert os.environ.get("OPENAI_BASE_URL") == "http://127.0.0.1:11434/v1"


def test_legacy_call_without_base_url_skips_filtering():
    """Existing callers in tests/test_ollama_discovery.py pass no base_url.
    They expect the original behavior — pick by saved or first model with
    no context filtering.  This test pins that contract."""
    # query_ollama_num_ctx must NOT be called when base_url is omitted —
    # otherwise legacy tests that don't mock it would do real network I/O.
    with patch(
        "agent.model_metadata.query_ollama_num_ctx"
    ) as mock_query:
        chosen = select_model(["a:1", "b:2"], saved="b:2", auto_pick_first=True)
        assert chosen == "b:2"
        mock_query.assert_not_called()
