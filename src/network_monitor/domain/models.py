from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DeviceSnapshot:
    observed_at: datetime
    name: str
    mac: str
    ip: str
    online: bool
    device_type: str | None = None
    connection_type: str | None = None
    download_speed: int | None = None
    upload_speed: int | None = None
    remain_time: int | None = None
    enable_priority: bool | None = None
    enable_internet: bool | None = None


@dataclass(slots=True)
class TrafficSnapshot:
    observed_at: datetime
    mac: str
    download_bytes: int | None
    upload_bytes: int | None
    source: str = "deco_traffic_stat"

    @property
    def total_bytes(self) -> int | None:
        if self.download_bytes is None and self.upload_bytes is None:
            return None
        return (self.download_bytes or 0) + (self.upload_bytes or 0)


@dataclass(slots=True)
class Device:
    mac: str
    first_seen: datetime
    last_seen: datetime
    name: str
    ip: str
    online: bool
    device_type: str | None = None
    connection_type: str | None = None


@dataclass(slots=True)
class PresenceSession:
    id: int | None
    mac: str
    started_at: datetime
    ended_at: datetime | None
    last_seen: datetime
    duration_seconds: int
