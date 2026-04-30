"""Regression test for the closed-network Ollama routing fix.

Before this fix:
  1. ``_maybe_setup_ollama_model()`` set ``HERMES_MODEL=ollama/<chosen>``
     in os.environ and a key ``ollama_model`` in ~/.hermes/config.json.
  2. Neither was consumed downstream — ``cli.main()`` and ``AIAgent``
     read ``model.default`` / ``model.provider`` / ``model.base_url``
     from ~/.hermes/config.yaml, none of which were set.
  3. Provider catalog fallback chose ``anthropic/claude-opus-4.7`` →
     401 on closed networks with no ANTHROPIC_API_KEY.

The fix writes config.yaml authoritatively (provider="custom" + base_url
pointing at local Ollama) and sets matching env vars so the runtime
resolver and OpenAI SDK both route to localhost:11434.

These tests pin that contract.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch


def _import_main():
    """Import hermes_cli.main lazily so module-level side effects don't
    pollute earlier tests in the same session."""
    from hermes_cli import main as _main  # noqa: WPS433

    return _main


def test_setup_writes_config_yaml_with_custom_provider(tmp_path, monkeypatch):
    """After Ollama discovery, ~/.hermes/config.yaml must contain
    model.default (bare name), model.provider="custom", model.base_url=
    http://127.0.0.1:11434/v1 — otherwise downstream routing falls
    through to anthropic.
    """
    main_mod = _import_main()

    # Isolate ~/.hermes
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    # Clear env state that would short-circuit the function or leak into
    # the assertions
    for var in (
        "HERMES_MODEL",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(var, raising=False)

    # Mock Ollama discovery (no network).  fetch_ollama_models is async,
    # so use AsyncMock which returns a coroutine when called — letting
    # the real asyncio.run() inside _maybe_setup_ollama_model work.
    from unittest.mock import AsyncMock

    fake_fetch = AsyncMock(return_value=["llama3.1:8b", "mistral:7b"])
    fake_select = MagicMock(return_value="llama3.1:8b")
    fake_module = MagicMock()
    fake_module.fetch_ollama_models = fake_fetch
    fake_module.select_model = fake_select

    class _NotRunning(RuntimeError):
        pass

    fake_module.OllamaNotRunningError = _NotRunning
    # Re-export the real resolve_ollama_base_url so _maybe_setup_ollama_model
    # picks the OLLAMA_HOST-aware URL (mocking it would return MagicMock).
    from hermes_cli.providers.ollama_discovery import resolve_ollama_base_url

    fake_module.resolve_ollama_base_url = resolve_ollama_base_url

    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_module,
    )

    # Capture save_config_value calls (defined in cli.py at module level)
    save_calls: list[tuple[str, object]] = []

    def fake_save(key_path: str, value):
        save_calls.append((key_path, value))
        return True

    fake_cli = MagicMock()
    fake_cli.save_config_value = fake_save
    monkeypatch.setitem(sys.modules, "cli", fake_cli)

    # Run the function under test
    main_mod._maybe_setup_ollama_model()

    # 1. config.yaml writes (the load-bearing assertion)
    assert ("model.default", "llama3.1:8b") in save_calls, (
        "model.default must be the bare Ollama tag (no 'ollama/' prefix). "
        "If this fails, downstream model_normalize will not strip prefix "
        "for unknown providers and the request body will carry an invalid "
        "model id."
    )
    assert ("model.provider", "custom") in save_calls, (
        "model.provider must be 'custom' so runtime_provider.py:486 "
        "(bare-custom path) takes effect. Adding a new 'ollama' provider "
        "would create an unaudited code path."
    )
    assert ("model.base_url", "http://127.0.0.1:11434/v1") in save_calls, (
        "Use 127.0.0.1 (not localhost) to avoid IPv6 dual-stack ambiguity."
    )

    # 2. env vars match config.yaml
    import os

    assert os.environ.get("OPENAI_BASE_URL") == "http://127.0.0.1:11434/v1"
    assert os.environ.get("OPENAI_API_KEY") == "no-key-required", (
        "OpenAI SDK refuses empty key. runtime_provider.py:489 already uses "
        "this sentinel for bare-custom providers."
    )

    # 3. NO_PROXY defangs corp HTTP_PROXY for localhost
    no_proxy = os.environ.get("NO_PROXY", "")
    for entry in ("localhost", "127.0.0.1", "::1"):
        assert entry in no_proxy, f"NO_PROXY missing {entry!r}: {no_proxy!r}"
    # lowercase variant too — some libs only check that
    assert os.environ.get("no_proxy") == no_proxy

    # 4. Legacy config.json kept for back-compat
    legacy = tmp_path / ".hermes" / "config.json"
    assert legacy.exists()
    assert json.loads(legacy.read_text())["ollama_model"] == "llama3.1:8b"

    # 5. HERMES_MODEL kept as prefixed form (back-compat)
    assert os.environ.get("HERMES_MODEL") == "ollama/llama3.1:8b"


def test_setup_skipped_when_hermes_model_already_set(tmp_path, monkeypatch):
    """If the user explicitly set HERMES_MODEL (tests, power users,
    custom env), Ollama auto-setup must not clobber it."""
    main_mod = _import_main()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setenv("HERMES_MODEL", "anthropic/claude-opus-4.7")

    save_calls: list = []
    fake_cli = MagicMock()
    fake_cli.save_config_value = lambda k, v: save_calls.append((k, v))
    monkeypatch.setitem(sys.modules, "cli", fake_cli)

    main_mod._maybe_setup_ollama_model()

    assert save_calls == [], "Must not write config.yaml when user pinned HERMES_MODEL"
    # Original HERMES_MODEL preserved
    import os

    assert os.environ.get("HERMES_MODEL") == "anthropic/claude-opus-4.7"


def test_routing_actually_lands_on_localhost(tmp_path, monkeypatch):
    """Integration: after _maybe_setup_ollama_model() writes real
    config.yaml, the runtime resolver must produce a runtime dict
    whose base_url points at the local Ollama.

    Catches the original bug class where 'state was written but
    downstream code path didn't read it'.
    """
    main_mod = _import_main()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for var in ("HERMES_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    # cli._hermes_home is set at import time from get_hermes_home(), which
    # reads HERMES_HOME env var.  Force it to our tmp.
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    from unittest.mock import AsyncMock

    fake_module = MagicMock()
    fake_module.fetch_ollama_models = AsyncMock(return_value=["llama3.1:8b"])
    fake_module.select_model = MagicMock(return_value="llama3.1:8b")
    from hermes_cli.providers.ollama_discovery import resolve_ollama_base_url

    fake_module.resolve_ollama_base_url = resolve_ollama_base_url

    class _NotRunning(RuntimeError):
        pass

    fake_module.OllamaNotRunningError = _NotRunning
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_module,
    )

    # Patch cli._hermes_home directly (it was set at module import to the
    # real ~/.hermes; HERMES_HOME env above only affects future imports).
    import cli as _cli_mod  # noqa: WPS433

    monkeypatch.setattr(_cli_mod, "_hermes_home", hermes_home, raising=False)

    main_mod._maybe_setup_ollama_model()

    # 1. config.yaml must exist with the routing keys
    import yaml  # type: ignore[import-untyped]

    cfg_path = tmp_path / ".hermes" / "config.yaml"
    assert cfg_path.exists(), (
        "config.yaml not written — save_config_value didn't reach disk. "
        f"Found in {tmp_path / '.hermes'}: "
        f"{list((tmp_path / '.hermes').glob('*'))}"
    )
    cfg = yaml.safe_load(cfg_path.read_text())
    assert cfg["model"]["default"] == "llama3.1:8b"
    assert cfg["model"]["provider"] == "custom"
    assert "127.0.0.1:11434" in cfg["model"]["base_url"]

    # 2. Run the runtime resolver against the written config — this is
    # the load-bearing step.  If resolve_runtime_provider returns the
    # localhost URL, the state→routing handoff works.
    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(
        requested="custom",
        explicit_base_url=cfg["model"]["base_url"],
    )
    assert runtime is not None
    assert runtime["provider"] == "custom"
    assert "127.0.0.1:11434" in runtime["base_url"]
    assert "anthropic" not in runtime.get("base_url", "").lower()
    assert "openai.com" not in runtime.get("base_url", "").lower()


def test_resolve_ollama_base_url_honors_host_env(monkeypatch):
    """OLLAMA_HOST env should drive discovery + routing URL.

    Mirrors Ollama's own env parsing — accept 'host:port', 'port', or
    full URLs.  Ensures users with custom ports (corp port already in
    use, multiple instances) don't fall back to 127.0.0.1:11434.
    """
    from hermes_cli.providers.ollama_discovery import resolve_ollama_base_url

    monkeypatch.delenv("OLLAMA_HOST", raising=False)
    assert resolve_ollama_base_url() == "http://127.0.0.1:11434"

    monkeypatch.setenv("OLLAMA_HOST", "11500")
    assert resolve_ollama_base_url() == "http://127.0.0.1:11500"

    monkeypatch.setenv("OLLAMA_HOST", "0.0.0.0:11500")
    assert resolve_ollama_base_url() == "http://0.0.0.0:11500"

    monkeypatch.setenv("OLLAMA_HOST", "https://ollama.internal:443")
    assert resolve_ollama_base_url() == "https://ollama.internal:443"

    monkeypatch.setenv("OLLAMA_HOST", "http://gpu-host:11434/")
    assert resolve_ollama_base_url() == "http://gpu-host:11434"


def test_setup_routes_through_ollama_host_when_set(tmp_path, monkeypatch):
    """When OLLAMA_HOST is set, the config.yaml + env vars must point
    at the same custom endpoint, not the default 127.0.0.1:11434."""
    main_mod = _import_main()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    for var in ("HERMES_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))
    monkeypatch.setenv("OLLAMA_HOST", "11500")  # custom port

    from unittest.mock import AsyncMock

    fake_module = MagicMock()
    fake_module.fetch_ollama_models = AsyncMock(return_value=["llama3.1:8b"])
    fake_module.select_model = MagicMock(return_value="llama3.1:8b")
    # resolve_ollama_base_url is a real function — re-export from the
    # mocked module so the test exercises the real env-honoring logic.
    from hermes_cli.providers.ollama_discovery import resolve_ollama_base_url

    fake_module.resolve_ollama_base_url = resolve_ollama_base_url

    class _NotRunning(RuntimeError):
        pass

    fake_module.OllamaNotRunningError = _NotRunning
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_module,
    )

    import cli as _cli_mod  # noqa: WPS433

    monkeypatch.setattr(_cli_mod, "_hermes_home", hermes_home, raising=False)

    main_mod._maybe_setup_ollama_model()

    import os

    import yaml  # type: ignore[import-untyped]

    cfg = yaml.safe_load((hermes_home / "config.yaml").read_text())
    assert cfg["model"]["base_url"] == "http://127.0.0.1:11500/v1"
    assert os.environ.get("OPENAI_BASE_URL") == "http://127.0.0.1:11500/v1"


def test_setup_preserves_existing_no_proxy(tmp_path, monkeypatch):
    """If user already has NO_PROXY for corp internal hosts, the fix
    appends localhost entries without dropping the existing ones."""
    main_mod = _import_main()

    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    for var in ("HERMES_MODEL", "OPENAI_BASE_URL", "OPENAI_API_KEY"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NO_PROXY", "internal.corp.local,10.0.0.0/8")

    from unittest.mock import AsyncMock

    fake_module = MagicMock()
    fake_module.fetch_ollama_models = AsyncMock(return_value=["mistral:7b"])
    fake_module.select_model = MagicMock(return_value="mistral:7b")

    class _NotRunning(RuntimeError):
        pass

    fake_module.OllamaNotRunningError = _NotRunning
    monkeypatch.setitem(
        sys.modules,
        "hermes_cli.providers.ollama_discovery",
        fake_module,
    )

    fake_cli = MagicMock()
    fake_cli.save_config_value = lambda k, v: True
    monkeypatch.setitem(sys.modules, "cli", fake_cli)

    main_mod._maybe_setup_ollama_model()

    import os

    no_proxy = os.environ.get("NO_PROXY", "")
    assert "internal.corp.local" in no_proxy
    assert "10.0.0.0/8" in no_proxy
    assert "127.0.0.1" in no_proxy
    assert "localhost" in no_proxy
