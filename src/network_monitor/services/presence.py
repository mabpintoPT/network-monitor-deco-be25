from __future__ import annotations

from datetime import datetime, timezone

from network_monitor.database.repository import NetworkRepository


class PresenceService:
    def __init__(self, repository: NetworkRepository) -> None:
        self.repository = repository

    def dashboard(self) -> dict:
        devices = self.repository.current_devices()
        sessions = self.repository.sessions(limit=10)
        now = datetime.now(timezone.utc)
        for device in devices:
            if device["online"]:
                device["since"] = self._open_session_start(device["mac"])
        return {"devices": devices, "recent_sessions": sessions, "now": now.isoformat()}

    def _open_session_start(self, mac: str) -> str | None:
        rows = self.repository.sessions(mac=mac, limit=1)
        if rows and rows[0]["ended_at"] is None:
            return rows[0]["started_at"]
        return None
