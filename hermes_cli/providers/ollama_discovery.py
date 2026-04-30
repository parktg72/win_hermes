"""Discover and select Ollama models running on localhost."""
from __future__ import annotations

import os
import sys
from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]

OLLAMA_BASE = "http://127.0.0.1:11434"  # 127.0.0.1 avoids IPv6 dual-stack
TIMEOUT = 2.0


class OllamaNotRunningError(RuntimeError):
    """Raised when Ollama is not reachable on localhost:11434."""


def resolve_ollama_base_url(default: str = OLLAMA_BASE) -> str:
    """Return the effective Ollama base URL, honoring ``OLLAMA_HOST``.

    Ollama itself reads the ``OLLAMA_HOST`` env var to decide where to
    listen (defaults to 127.0.0.1:11434).  If a user has bound it to a
    custom port (corp port already in use, multiple instances, etc.),
    discovery + routing must follow.

    Accepted formats (mirrors Ollama's own parsing):
      - "http://host:port"   — used as-is
      - "https://host:port"  — used as-is
      - "host:port"          — http:// prefixed
      - "port"               — bound to 127.0.0.1:<port>
    """
    raw = (os.environ.get("OLLAMA_HOST") or "").strip()
    if not raw:
        return default
    if "://" in raw:
        return raw.rstrip("/")
    if raw.isdigit():
        return f"http://127.0.0.1:{raw}"
    return f"http://{raw}".rstrip("/")


async def fetch_ollama_models(base_url: Optional[str] = None) -> list[str]:
    """Return list of model names from running Ollama instance.

    Args:
        base_url: Override discovery URL.  Defaults to
            :func:`resolve_ollama_base_url` (which honors
            ``OLLAMA_HOST``).  Tests pass an explicit URL.

    Raises:
        OllamaNotRunningError: if Ollama is not reachable.
    """
    if httpx is None:
        raise ImportError("httpx is required for Ollama discovery")

    target = base_url or resolve_ollama_base_url()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            resp = await client.get(f"{target}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            return [m["name"] for m in data.get("models", [])]
    except httpx.HTTPStatusError as exc:
        raise OllamaNotRunningError(
            f"Ollama 서버가 오류를 반환했습니다 (HTTP {exc.response.status_code}). "
            f"`ollama serve`를 재시작 후 다시 시도하세요."
        ) from exc
    except httpx.HTTPError as exc:
        raise OllamaNotRunningError(
            "Ollama가 실행되지 않았습니다. `ollama serve` 실행 후 재시작하세요."
        ) from exc


def select_model(
    models: list[str],
    saved: Optional[str],
    *,
    auto_pick_first: bool = False,
) -> str:
    """Return the model to use, prompting if needed.

    Args:
        models: Available model names from Ollama.
        saved: Last-used model name from config (may be None or stale).
        auto_pick_first: If True, skip interactive prompt (for tests).

    Returns:
        Selected model name.

    Raises:
        ValueError: If models list is empty.
    """
    if not models:
        raise ValueError("No models found in Ollama. Run `ollama pull <model>` first.")

    if saved and saved in models:
        return saved

    if auto_pick_first or not sys.stdin.isatty():
        return models[0]

    print("\nOllama 모델을 선택하세요:")
    for i, name in enumerate(models, 1):
        print(f"  {i}. {name}")

    while True:
        try:
            choice = input(f"번호 입력 [1-{len(models)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                return models[idx]
        except (ValueError, EOFError):
            pass
        print(f"1에서 {len(models)} 사이의 번호를 입력하세요.")
