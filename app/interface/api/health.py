"""Health probes.

- /health        liveness: process is up. No external deps -> always green.
- /health/ready  readiness: can we actually reach Postgres + Redis?
                 Returns 503 if any dependency is down.
"""

from fastapi import APIRouter, Response
from sqlalchemy import text

from app.infrastructure.db import engine
from app.infrastructure.redis import redis_client

router = APIRouter(tags=["health"])


@router.get("/health")
async def liveness() -> dict:
    return {"status": "ok"}


@router.get("/health/ready")
async def readiness(response: Response) -> dict:
    checks: dict[str, str] = {}

    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as exc:  # noqa: BLE001 — surface the failure class to the probe
        checks["postgres"] = f"error: {exc.__class__.__name__}"

    try:
        await redis_client.ping()
        checks["redis"] = "ok"
    except Exception as exc:  # noqa: BLE001
        checks["redis"] = f"error: {exc.__class__.__name__}"

    healthy = all(v == "ok" for v in checks.values())
    response.status_code = 200 if healthy else 503
    return {"status": "ok" if healthy else "degraded", "checks": checks}
