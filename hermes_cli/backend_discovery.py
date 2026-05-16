"""Multi-backend auto-discovery for Windows non-developer users.

Background
----------
Earlier in this fork, ``_maybe_setup_ollama_model()`` assumed every user
was on a closed-network Korean medical-research PC with only Ollama.
That assumption is too narrow — some users have Anthropic / OpenAI /
Gemini keys (or Codex OAuth) and want hermes to "just work" with the
backend they already pay for, without dropping into a wizard.

This module centralizes "what LLM backends are available to me right now"
so that ``_maybe_setup_default_backend()`` (in ``hermes_cli.main``) can
either auto-pick the only one, or show a Korean picker when multiple
options coexist.

Detection priority (= picker display order):
    1. Anthropic Claude   — ANTHROPIC_API_KEY / ANTHROPIC_TOKEN /
                            CLAUDE_CODE_OAUTH_TOKEN env
    2. OpenAI             — OPENAI_API_KEY env (excluding our
                            "no-key-required" Ollama sentinel)
    3. OpenAI Codex OAuth — ~/.codex/auth.json with valid tokens
    4. Google Gemini      — GEMINI_API_KEY / GOOGLE_API_KEY env or
                            ~/.gemini/oauth_creds.json
    5. Ollama (local)     — localhost:11434 reachable AND ≥1 model

Each detection function is best-effort and silently returns None on
any failure (no exceptions propagate to the picker).  Phase-1 invariants
hold: Ollama path still routes through ``provider="custom"``, env-driven
overrides still win, and the 64K context guard from
``test_ollama_picker_context_guard.py`` is reused for the Ollama probe,
but small-context local Ollama models are still offered in degraded mode.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

# Sentinel that ``_maybe_setup_ollama_model`` writes to OPENAI_API_KEY when
# it routes through localhost Ollama (runtime_provider.py:489 mirrors this).
# Treat it as "no real OpenAI key" for backend-discovery purposes — otherwise
# Phase-1 Ollama setups would falsely trigger the "OpenAI detected" branch.
_OLLAMA_SENTINEL_KEYS = {"no-key-required", ""}


# ─────────────────────────────────────────────────────────────────────
# BackendOption — what the picker shows / what config.yaml writes
# ─────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class BackendOption:
    """One usable LLM backend the user could pick."""

    id: str  # config-yaml ``model.provider`` value
    label: str  # Korean-friendly display string
    detail: str  # short detection reason (env var name, file path, etc.)
    base_url: Optional[str] = None  # only set for the local Ollama / custom path
    # NOTE: deliberately no ``suggested_model`` field.  Hardcoding model
    # names here (claude-sonnet-4-6, gpt-5.4, gemini-2.5-pro) goes stale
    # the moment a vendor ships a new flagship.  Instead, `_maybe_setup_
    # default_backend` writes only ``model.provider`` and lets the
    # existing ``get_default_model_for_provider`` (hermes_cli/models.py)
    # resolve the model at AIAgent init time.  Loud failure with a known
    # error path > silent 400 from a stale name.


# ─────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────


def _has_env_token(*names: str) -> bool:
    """True if at least one env var is set to a real token (not blank,
    not our Ollama sentinel)."""
    for name in names:
        raw = os.environ.get(name)
        if raw is None:
            continue
        val = raw.strip()
        if val and val.lower() not in _OLLAMA_SENTINEL_KEYS:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────
# Detection functions — one per backend, best-effort, return None on failure
# ─────────────────────────────────────────────────────────────────────


def _detect_anthropic() -> Optional[BackendOption]:
    """ANTHROPIC_API_KEY / ANTHROPIC_TOKEN / CLAUDE_CODE_OAUTH_TOKEN."""
    if _has_env_token(
        "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN", "CLAUDE_CODE_OAUTH_TOKEN"
    ):
        return BackendOption(
            id="anthropic",
            label="Anthropic Claude",
            detail="ANTHROPIC_API_KEY 또는 OAuth 토큰 감지됨",
        )
    return None


def _detect_openai() -> Optional[BackendOption]:
    """OPENAI_API_KEY env (excluding the Ollama sentinel)."""
    if _has_env_token("OPENAI_API_KEY"):
        return BackendOption(
            id="openai",
            label="OpenAI",
            detail="OPENAI_API_KEY 감지됨",
        )
    return None


def _detect_codex_oauth() -> Optional[BackendOption]:
    """``codex login`` writes ~/.codex/auth.json with refresh tokens."""
    auth_path = Path.home() / ".codex" / "auth.json"
    try:
        if not auth_path.exists():
            return None
        data = json.loads(auth_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    tokens = data.get("tokens") if isinstance(data, dict) else None
    if isinstance(tokens, dict) and (
        tokens.get("access_token") or tokens.get("id_token")
    ):
        return BackendOption(
            id="openai-codex",
            label="OpenAI Codex (ChatGPT 로그인)",
            detail="~/.codex/auth.json 유효",
        )
    return None


def _detect_gemini() -> Optional[BackendOption]:
    """GEMINI_API_KEY / GOOGLE_API_KEY env, or ~/.gemini/oauth_creds.json."""
    if _has_env_token("GEMINI_API_KEY", "GOOGLE_API_KEY"):
        return BackendOption(
            id="gemini",
            label="Google Gemini",
            detail="GEMINI_API_KEY 감지됨",
        )
    oauth = Path.home() / ".gemini" / "oauth_creds.json"
    try:
        if oauth.exists() and oauth.stat().st_size > 0:
            return BackendOption(
                id="gemini",
                label="Google Gemini (OAuth)",
                detail="~/.gemini/oauth_creds.json 유효",
            )
    except OSError:
        pass
    return None


def _detect_ollama() -> Optional[BackendOption]:
    """Probe localhost Ollama and return it when at least one model exists.

    Closed-network Windows users may only have a small model such as
    gemma2:latest available.  Treat that as an available backend and let
    the model picker/runtime run in small-context degraded mode.
    """
    import asyncio

    try:
        from hermes_cli.providers.ollama_discovery import (
            OllamaNotRunningError,
            fetch_ollama_models,
            resolve_ollama_base_url,
        )
    except Exception:  # noqa: BLE001 — provider module import errors
        return None

    base = resolve_ollama_base_url()  # honors OLLAMA_HOST
    base_v1 = f"{base}/v1"

    try:
        models = asyncio.run(fetch_ollama_models(base_url=base))
    except OllamaNotRunningError:
        return None
    except Exception:  # noqa: BLE001 — network errors
        return None

    if not models:
        return None

    try:
        from agent.model_metadata import (
            MINIMUM_CONTEXT_LENGTH,
            query_ollama_num_ctx,
        )
    except Exception:  # noqa: BLE001 — metadata module not importable
        # Degrade gracefully — assume Ollama is fine if it has any models.
        # Phase-1 picker will reject sub-64K at the model-selection step.
        return BackendOption(
            id="custom",
            label=f"Ollama (로컬, {len(models)}개 모델)",
            detail=f"{base} 응답",
            base_url=base_v1,
        )

    has_compatible = False
    for name in models:
        try:
            ctx = query_ollama_num_ctx(name, base_v1)
        except Exception:  # noqa: BLE001 — /api/show variants
            ctx = None
        # Unknown context → compatible-by-faith (matches Phase-1 picker)
        if ctx is None or ctx >= MINIMUM_CONTEXT_LENGTH:
            has_compatible = True
            break

    if not has_compatible:
        return BackendOption(
            id="custom",
            label=f"Ollama (로컬, {len(models)}개 모델)",
            detail=f"{base} 응답, 작은 컨텍스트 모델만 감지됨",
            base_url=base_v1,
        )

    return BackendOption(
        id="custom",
        label=f"Ollama (로컬, {len(models)}개 모델)",
        detail=f"{base} 응답, 64K+ 컨텍스트 모델 1개 이상",
        base_url=base_v1,
    )


# Module-level registry so tests can replace individual detectors without
# patching the whole list (and so callers can iterate in priority order).
_DETECTORS: tuple[Callable[[], Optional[BackendOption]], ...] = (
    _detect_anthropic,
    _detect_openai,
    _detect_codex_oauth,
    _detect_gemini,
    _detect_ollama,
)


def detect_available_backends() -> list[BackendOption]:
    """Return the list of usable backends in display priority order.

    Best-effort: any detector raising returns nothing for that backend
    (logged as None — never propagates).  The picker downstream decides
    whether the list is empty / one / many.
    """
    out: list[BackendOption] = []
    for detector in _DETECTORS:
        try:
            opt = detector()
        except Exception:  # noqa: BLE001 — discovery never fails the user
            opt = None
        if opt is not None:
            out.append(opt)
    return out
