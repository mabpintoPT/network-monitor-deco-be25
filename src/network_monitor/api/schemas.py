from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    collector_enabled: bool
    collector_interval: int
    database: str
