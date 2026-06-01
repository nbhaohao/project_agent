"""Run submission & query endpoints."""

import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from app.application.agent.events import derive_events
from app.application.run_service import RunService
from app.domain.message import RunMessage
from app.domain.run import Run, RunStatus
from app.infrastructure.db import SessionLocal
from app.infrastructure.redis import redis_client
from app.infrastructure.repositories import SqlAlchemyMessageRepository, SqlAlchemyRunRepository
from app.interface.api.deps import get_run_service

_TERMINAL = {RunStatus.SUCCEEDED, RunStatus.FAILED}

router = APIRouter(prefix="/runs", tags=["runs"])


class SubmitRunRequest(BaseModel):
    input: str


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    input: str
    status: RunStatus
    created_at: datetime
    result: str | None = None
    error: str | None = None


@router.post("", response_model=RunResponse, status_code=201)
async def submit_run(
    body: SubmitRunRequest,
    service: RunService = Depends(get_run_service),
) -> RunResponse:
    run = await service.submit(body.input)
    return RunResponse.model_validate(run)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: uuid.UUID,
    service: RunService = Depends(get_run_service),
) -> RunResponse:
    run = await service.get(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunResponse.model_validate(run)


@router.get("/{run_id}/events")
async def run_events(run_id: uuid.UUID) -> StreamingResponse:
    async with SessionLocal() as session, session.begin():
        run = await SqlAlchemyRunRepository(session).get(run_id)
        if run is None:
            raise HTTPException(status_code=404, detail="run not found")
        history = await SqlAlchemyMessageRepository(session).list_for_run(run_id)
    # session released — do not hold DB connection during streaming

    return StreamingResponse(
        _event_stream(run, history),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _event_stream(run: Run, history: list[RunMessage]) -> AsyncIterator[str]:
    def _sse(event: dict) -> str:
        return f"data: {json.dumps(event)}\n\n"

    # replay history so late-connecting clients see all steps
    for msg in history:
        for event in derive_events(msg):
            yield _sse(event)

    # already finished — send terminal event and close immediately
    if run.status in _TERMINAL:
        if run.status == RunStatus.SUCCEEDED:
            yield _sse({"type": "done", "result": run.result or ""})
        else:
            yield _sse({"type": "error", "error": run.error or ""})
        return

    # subscribe to real-time events from worker
    pubsub = redis_client.pubsub()
    await pubsub.subscribe(f"run:{run.id}:events")
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            data = message["data"]
            if isinstance(data, bytes):
                data = data.decode()
            event = json.loads(data)
            yield _sse(event)
            if event.get("type") in ("done", "error"):
                break
    finally:
        await pubsub.unsubscribe(f"run:{run.id}:events")
        await pubsub.aclose()


@router.get("", response_model=list[RunResponse])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: RunService = Depends(get_run_service),
) -> list[RunResponse]:
    runs = await service.list(limit=limit, offset=offset)
    return [RunResponse.model_validate(r) for r in runs]
