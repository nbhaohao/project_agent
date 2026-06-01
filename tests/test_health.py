"""Liveness probe — dependency-free, so this is the first always-green test."""

from httpx import ASGITransport, AsyncClient

from app.main import app


async def test_liveness_returns_ok():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
