from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from network_monitor.api.schemas import HealthResponse
from network_monitor.settings import settings

router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=HealthResponse)
def health(app_state):
    return HealthResponse(
        status="ok",
        collector_enabled=settings.collector_enabled,
        collector_interval=settings.collector_interval,
        database=str(app_state.repository.db.path),
    )
