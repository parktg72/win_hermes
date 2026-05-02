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


def _query_ollama_contexts(
    models: list[str], base_url: str
) -> dict[str, Optional[int]]:
    """Best-effort: query num_ctx for each model.  Returns ``{name: ctx_or_None}``.

    Used by :func:`select_model` to filter models below
    :data:`agent.model_metadata.MINIMUM_CONTEXT_LENGTH` from the picker.
    Failures (server-down race, /api/show error, etc.) yield ``None`` for
    that model — the caller treats unknown as compatible-by-faith so the
    picker doesn't go empty on a transient hiccup.
    """
    from agent.model_metadata import query_ollama_num_ctx

    out: dict[str, Optional[int]] = {}
    for name in models:
        try:
            out[name] = query_ollama_num_ctx(name, base_url)
        except Exception:  # noqa: BLE001 — upstream raises a wide set
            out[name] = None
    return out


def _format_picker_line(
    index: int, name: str, ctx: Optional[int], minimum: int
) -> str:
    """Format one row of the picker so users see compat status at a glance."""
    if ctx is None:
        return f"  {index}. ? {name}  (컨텍스트 조회 실패 — 일단 시도 가능)"
    if ctx >= minimum:
        return f"  {index}. {name}  (컨텍스트 {ctx:,} 토큰)"
    # Below minimum — clearly mark
    return (
        f"  {index}. ⚠ {name}  (컨텍스트 {ctx:,} 토큰 — "
        f"{minimum // 1000}K 미만, 사용 불가)"
    )


def _no_compatible_models_error(
    contexts: dict[str, Optional[int]], minimum: int
) -> str:
    """Korean-language guide when every installed model is below the minimum."""
    lines = [
        f"Hermes Agent 는 컨텍스트 {minimum:,} 토큰 이상의 Ollama 모델이 필요합니다.",
        "현재 설치된 모델은 모두 그 미만이라 채팅이 시작되지 않습니다:",
    ]
    for name, ctx in contexts.items():
        ctx_str = f"{ctx:,}" if ctx else "?"
        lines.append(f"  - {name} (컨텍스트 {ctx_str} 토큰)")
    lines.append("")
    lines.append("다음 중 하나를 받은 뒤 hermes 를 다시 실행해 주세요:")
    lines.append("  ollama pull gemma3:12b      :: 한국어 강함, 128K, 약 8GB")
    lines.append("  ollama pull llama3.1:8b     :: 한국어 가능, 128K, 약 5GB")
    lines.append("  ollama pull qwen3:8b        :: 한국어 가능, 128K, 약 5GB")
    return "\n".join(lines)


def select_model(
    models: list[str],
    saved: Optional[str],
    *,
    auto_pick_first: bool = False,
    base_url: Optional[str] = None,
) -> str:
    """Return the model to use, prompting if needed.

    Args:
        models: Available model names from Ollama.
        saved: Last-used model name from config (may be None or stale).
        auto_pick_first: If True, skip interactive prompt (for tests).
        base_url: When provided, query each model's num_ctx and reject
            those below ``MINIMUM_CONTEXT_LENGTH`` (64K) so the user
            never picks a model that hermes will refuse at init time.
            When ``None``, fall back to legacy behavior (no filtering)
            so existing unit tests keep passing without rewiring.

    Returns:
        Selected model name (guaranteed compatible when ``base_url`` is set).

    Raises:
        ValueError: If models list is empty, or every model is below the
            minimum context length (with Korean guidance and pull commands).
    """
    if not models:
        raise ValueError("No models found in Ollama. Run `ollama pull <model>` first.")

    # Legacy path: no base_url → skip context filtering (preserves existing
    # test contracts in test_ollama_discovery.py).
    if not base_url:
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

    # Context-aware path: query num_ctx and filter by 64K minimum.
    from agent.model_metadata import MINIMUM_CONTEXT_LENGTH

    contexts = _query_ollama_contexts(models, base_url)

    def _is_compat(name: str) -> bool:
        ctx = contexts.get(name)
        # Unknown context → treat as compatible (don't block on transient
        # /api/show failure).  Below-min → reject.
        return ctx is None or ctx >= MINIMUM_CONTEXT_LENGTH

    compatible = [m for m in models if _is_compat(m)]

    if not compatible:
        raise ValueError(_no_compatible_models_error(contexts, MINIMUM_CONTEXT_LENGTH))

    # Saved model still valid?
    if saved and saved in compatible:
        return saved
    if saved and saved in models and saved not in compatible:
        ctx = contexts.get(saved)
        ctx_str = f"{ctx:,}" if ctx else "?"
        print(
            f"\n⚠ 이전에 사용한 '{saved}' (컨텍스트 {ctx_str} 토큰) 는 "
            f"{MINIMUM_CONTEXT_LENGTH // 1000}K 미만이라 사용할 수 없습니다.\n"
            f"  다른 모델을 선택해 주세요."
        )

    if auto_pick_first or not sys.stdin.isatty():
        return compatible[0]

    print(
        f"\nOllama 모델을 선택하세요 "
        f"({MINIMUM_CONTEXT_LENGTH // 1000}K+ 컨텍스트 모델만 선택 가능):"
    )
    for i, name in enumerate(models, 1):
        print(_format_picker_line(i, name, contexts.get(name), MINIMUM_CONTEXT_LENGTH))

    while True:
        try:
            choice = input(f"번호 입력 [1-{len(models)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(models):
                chosen = models[idx]
                if _is_compat(chosen):
                    return chosen
                ctx = contexts.get(chosen)
                ctx_str = f"{ctx:,}" if ctx else "?"
                print(
                    f"⚠ '{chosen}' 는 컨텍스트가 {ctx_str} 토큰이라 "
                    f"사용할 수 없습니다.\n"
                    f"  64K 이상 모델을 선택해 주세요."
                )
                continue
        except (ValueError, EOFError):
            pass
        print(f"1에서 {len(models)} 사이의 번호를 입력하세요.")
