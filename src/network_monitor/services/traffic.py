from __future__ import annotations

from network_monitor.database.repository import NetworkRepository


class TrafficService:
    """Apresenta tráfego cumulativo recolhido pela API local da Deco."""

    def __init__(self, repository: NetworkRepository) -> None:
        self.repository = repository

    def device_samples(self, mac: str, limit: int = 500) -> list[dict]:
        return self.repository.traffic_samples(mac, limit=limit)
