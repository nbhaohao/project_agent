"""SiliconFlowEmbedder — inject mock client, no real network calls."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.infrastructure.embedder import SiliconFlowEmbedder


def _fake_client(vector: list[float]) -> AsyncMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.json.return_value = {"data": [{"embedding": vector, "index": 0}]}
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post.return_value = resp
    return client


async def test_embed_returns_vector():
    vector = [0.1] * 1024
    embedder = SiliconFlowEmbedder(client=_fake_client(vector))
    result = await embedder.embed("hello world")

    assert result == vector
    assert len(result) == 1024


async def test_embed_passes_correct_payload():
    client = _fake_client([0.0] * 1024)
    embedder = SiliconFlowEmbedder(client=client)
    await embedder.embed("hello world")

    call_kwargs = client.post.call_args
    assert call_kwargs.args[0] == "/embeddings"
    assert call_kwargs.kwargs["json"]["input"] == "hello world"
    assert call_kwargs.kwargs["json"]["encoding_format"] == "float"


async def test_embed_raises_on_http_error():
    resp = MagicMock()
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=MagicMock()
    )
    client = AsyncMock(spec=httpx.AsyncClient)
    client.post.return_value = resp

    embedder = SiliconFlowEmbedder(client=client)
    with pytest.raises(httpx.HTTPStatusError):
        await embedder.embed("bad request")
