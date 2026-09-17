from __future__ import annotations

from network_monitor.database.repository import NetworkRepository


class DeviceService:
    def __init__(self, repository: NetworkRepository) -> None:
        self.repository = repository

    def list(self) -> list[dict]:
        return self.repository.current_devices()

    def detail(self, mac: str) -> dict | None:
        devices = [d for d in self.repository.current_devices() if d["mac"].lower() == mac.lower()]
        if not devices:
            return None
        device = devices[0]
        device["sessions"] = self.repository.sessions(mac, limit=200)
        return device
