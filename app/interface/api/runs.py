"""Run submission & query endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict

from app.application.run_service import RunService
from app.domain.run import RunStatus
from app.interface.api.deps import get_run_service

router = APIRouter(prefix="/runs", tags=["runs"])


class SubmitRunRequest(BaseModel):
    input: str


class RunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    input: str
    status: RunStatus
    created_at: datetime


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


@router.get("", response_model=list[RunResponse])
async def list_runs(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    service: RunService = Depends(get_run_service),
) -> list[RunResponse]:
    runs = await service.list(limit=limit, offset=offset)
    return [RunResponse.model_validate(r) for r in runs]
