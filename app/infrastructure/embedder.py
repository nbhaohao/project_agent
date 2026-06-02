"""SiliconFlow embedding adapter — OpenAI-compatible /embeddings endpoint."""

import httpx

from app.config import settings


class SiliconFlowEmbedder:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.embedding_base_url,
            headers={"Authorization": f"Bearer {settings.embedding_api_key}"},
            timeout=30.0,
        )

    async def embed(self, text: str) -> list[float]:
        response = await self._client.post(
            "/embeddings",
            json={
                "model": settings.embedding_model,
                "input": text,
                "encoding_format": "float",
            },
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
