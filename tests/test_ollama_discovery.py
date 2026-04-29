import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from hermes_cli.providers.ollama_discovery import (
    fetch_ollama_models,
    select_model,
    OllamaNotRunningError,
)


@pytest.mark.asyncio
async def test_fetch_ollama_models_returns_list():
    fake_response = {"models": [{"name": "llama3.2:latest"}, {"name": "mistral:7b"}]}
    mock_resp = AsyncMock()
    mock_resp.json = MagicMock(return_value=fake_response)
    mock_resp.raise_for_status = MagicMock()

    with patch("hermes_cli.providers.ollama_discovery.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(return_value=MagicMock(
            get=AsyncMock(return_value=mock_resp)
        ))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        models = await fetch_ollama_models()

    assert models == ["llama3.2:latest", "mistral:7b"]


@pytest.mark.asyncio
async def test_fetch_ollama_models_raises_when_not_running():
    import httpx
    with patch("hermes_cli.providers.ollama_discovery.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=httpx.ConnectError("refused"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(OllamaNotRunningError):
            await fetch_ollama_models()


@pytest.mark.asyncio
async def test_fetch_ollama_models_raises_on_read_error():
    import httpx
    with patch("hermes_cli.providers.ollama_discovery.httpx.AsyncClient") as mock_client:
        mock_client.return_value.__aenter__ = AsyncMock(side_effect=httpx.ReadError("connection reset"))
        mock_client.return_value.__aexit__ = AsyncMock(return_value=False)
        with pytest.raises(OllamaNotRunningError):
            await fetch_ollama_models()


def test_select_model_saved_empty_string_falls_through():
    result = select_model(["mistral:7b"], saved="", auto_pick_first=True)
    assert result == "mistral:7b"


def test_select_model_saved_none_picks_first():
    result = select_model(["mistral:7b", "llama3.2:latest"], saved=None, auto_pick_first=True)
    assert result == "mistral:7b"


def test_select_model_returns_saved_when_valid():
    models = ["llama3.2:latest", "mistral:7b"]
    result = select_model(models, saved="llama3.2:latest")
    assert result == "llama3.2:latest"


def test_select_model_ignores_stale_saved():
    models = ["mistral:7b"]
    # saved model no longer exists in Ollama
    result = select_model(models, saved="llama3.2:latest", auto_pick_first=True)
    assert result == "mistral:7b"


def test_select_model_raises_on_empty_list():
    with pytest.raises(ValueError, match="No models"):
        select_model([], saved=None)
