"""Egress guard tests for the closed-network Ollama-only setup.

Goal: lock in that after `_maybe_setup_ollama_model()` runs, every
significant routing decision lands on localhost — no decision branch
silently routes to api.anthropic.com / api.openai.com / openrouter.ai.

Two layers of test:

1. Routing-decision tests (cheap, deterministic) — exercise the
   resolution helpers directly and assert the returned base_url stays
   on 127.0.0.1.

2. Socket-level guard (broad, paranoid) — monkey-patch
   ``socket.socket.connect`` to fail any non-loopback address, then
   exercise the routing helpers.  If any code path attempts to open a
   real connection to an external host, it raises immediately instead
   of silently succeeding offline (which can mask a leak in the field
   when corp DNS happens to resolve and the proxy holds the request).

These guard the win_hermes invariant per CLAUDE.md §3.3:
"Ollama 미실행 / PyPI 차단 등은 한국어 메시지 + exit(1)" — meaning
zero successful external HTTP under the closed-network end-user.
"""
from __future__ import annotations

import socket
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest


# ─────────────────────────────────────────────────────────────────────
# Shared fixture: run _maybe_setup_ollama_model in an isolated home
# ─────────────────────────────────────────────────────────────────────


@pytest.fixture
def ollama_session(tmp_path, monkeypatch):
    """Set up a tmp ~/.hermes/, run _maybe_setup_ollama_model() with a
    mocked Ollama discovery, and yield (chosen_model, base_url, hermes_home)."""
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    for var in (
        "HERMES_MODEL",
        "OPENAI_BASE_URL",
        "OPENAI_API_KEY",
        "OPENROUTER_API_KEY",
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_TOKEN",
        "NO_PROXY",
        "no_proxy",
    ):
        monkeypatch.delenv(var, raising=False)

    hermes_home = tmp_path / ".hermes"
    hermes_home.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HERMES_HOME", str(hermes_home))

    fake_module = MagicMock()
    fake_module.fetch_ollama_models = AsyncMock(return_value=["llama3.1:8b"])
    fake_module.select_model = MagicMock(return_value="llama3.1:8b")

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

    from hermes_cli import main as main_mod

    main_mod._maybe_setup_ollama_model()

    yield ("llama3.1:8b", "http://127.0.0.1:11434/v1", hermes_home)


# ─────────────────────────────────────────────────────────────────────
# Routing-decision tests
# ─────────────────────────────────────────────────────────────────────


def test_runtime_provider_resolves_to_localhost(ollama_session):
    """resolve_runtime_provider for the 'custom' request must return a
    runtime dict with base_url on 127.0.0.1."""
    chosen, base_url, _ = ollama_session

    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(
        requested="custom",
        explicit_base_url=base_url,
    )
    assert runtime is not None
    assert runtime["provider"] == "custom"
    assert "127.0.0.1" in runtime["base_url"]
    for forbidden in ("anthropic", "openai.com", "openrouter.ai", "google"):
        assert forbidden not in runtime["base_url"].lower()


def test_account_usage_skips_for_custom_provider(ollama_session):
    """fetch_account_usage('custom', ...) must return None without
    attempting any HTTP — provider='custom' is the closed-network
    sentinel that account_usage.py:315 explicitly excludes.
    """
    from agent.account_usage import fetch_account_usage

    snapshot = fetch_account_usage("custom", base_url="http://127.0.0.1:11434/v1")
    assert snapshot is None

    # And for the empty/auto cases too — the same exclusion path
    assert fetch_account_usage("", base_url=None) is None
    assert fetch_account_usage("auto", base_url=None) is None


def test_no_anthropic_or_openai_referenced_in_config(ollama_session):
    """Spot-check the written config.yaml — none of the routing-relevant
    keys should still hold an anthropic / openai-cloud URL or model name.
    """
    import yaml  # type: ignore[import-untyped]

    _, _, hermes_home = ollama_session
    cfg_path = hermes_home / "config.yaml"
    assert cfg_path.exists()
    cfg_text = cfg_path.read_text()

    # Permit the literal substring "anthropic" inside *unrelated* config
    # keys that may have shipped from cli-config.yaml.example.  But the
    # routing-relevant model.* keys must not leak.
    cfg = yaml.safe_load(cfg_text) or {}
    model_section = cfg.get("model", {})
    routing_str = str(model_section).lower()
    for forbidden in ("anthropic", "claude-opus", "openai.com", "openrouter"):
        assert forbidden not in routing_str, (
            f"config.yaml model.* leaked {forbidden!r}: {model_section!r}"
        )


# ─────────────────────────────────────────────────────────────────────
# Socket-level guard
# ─────────────────────────────────────────────────────────────────────


_LOOPBACK_PREFIXES = ("127.", "::1", "localhost")


class _EgressViolation(AssertionError):
    """Raised when test code attempts to reach a non-loopback address."""


def _is_loopback(addr) -> bool:
    """Return True if addr (host or sockaddr tuple) is a loopback host."""
    if isinstance(addr, tuple) and addr:
        host = addr[0]
    else:
        host = addr
    if not isinstance(host, str):
        return False
    host_lower = host.lower()
    return any(host_lower.startswith(p) for p in _LOOPBACK_PREFIXES)


def test_routing_does_not_open_external_sockets(ollama_session, monkeypatch):
    """Patch socket.socket.connect to record every address tuple; if
    any non-loopback connection is attempted during routing-decision
    code, fail loudly.  (Routing decisions ought to be pure config /
    metadata reads — no I/O.)
    """
    chosen, base_url, _ = ollama_session

    attempts: list = []
    real_connect = socket.socket.connect

    def guarded_connect(self, address, *args, **kwargs):
        attempts.append(address)
        if not _is_loopback(address):
            raise _EgressViolation(
                f"non-loopback connect attempted: {address!r}"
            )
        return real_connect(self, address, *args, **kwargs)

    monkeypatch.setattr(socket.socket, "connect", guarded_connect)

    # Exercise the routing-decision code paths most likely to leak.
    from hermes_cli.runtime_provider import resolve_runtime_provider

    runtime = resolve_runtime_provider(
        requested="custom",
        explicit_base_url=base_url,
    )
    assert runtime is not None  # smoke

    from agent.account_usage import fetch_account_usage

    fetch_account_usage("custom", base_url=base_url)
    fetch_account_usage("", base_url=None)
    fetch_account_usage("auto", base_url=None)

    # If we got here without _EgressViolation, the assertion below is
    # tautological — but keep it explicit for the test's intent.
    non_loopback = [a for a in attempts if not _is_loopback(a)]
    assert not non_loopback, (
        f"routing decisions opened sockets to non-loopback hosts: {non_loopback!r}"
    )
