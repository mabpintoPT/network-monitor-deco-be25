from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from network_monitor.collectors.base import Collector
from network_monitor.collectors.deco.client import DecoClient
from network_monitor.domain.models import DeviceSnapshot, TrafficSnapshot

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class DecoCollection:
    snapshots: list[DeviceSnapshot]
    traffic: list[TrafficSnapshot]
    traffic_error: str | None = None


class DecoCollector(Collector):
    """Recolhe presença e tráfego dos clientes da Deco."""

    def __init__(self, client: DecoClient) -> None:
        self.client = client

    def collect(self) -> list[DeviceSnapshot]:
        """Compatibilidade com a V1: recolhe apenas presença."""
        observed_at = datetime.now(timezone.utc)
        clients = self.client.get_clients()
        return [self._snapshot(client, observed_at) for client in clients]

    def collect_bundle(self) -> DecoCollection:
        """Faz uma recolha completa sem deixar uma falha de tráfego quebrar presença."""
        observed_at = datetime.now(timezone.utc)
        clients = self.client.get_clients()
        snapshots = [self._snapshot(client, observed_at) for client in clients]

        traffic: list[TrafficSnapshot] = []
        traffic_error: str | None = None
        try:
            stats = self.client.get_traffic_stats()
            traffic = [
                TrafficSnapshot(
                    observed_at=observed_at,
                    mac=stat.mac,
                    download_bytes=stat.download_bytes,
                    upload_bytes=stat.upload_bytes,
                )
                for stat in stats
            ]
        except Exception as exc:  # tráfego é complementar à presença
            traffic_error = str(exc)
            logger.warning("Falha na recolha de tráfego: %s", exc)

        return DecoCollection(
            snapshots=snapshots,
            traffic=traffic,
            traffic_error=traffic_error,
        )

    @staticmethod
    def _snapshot(client, observed_at: datetime) -> DeviceSnapshot:
        return DeviceSnapshot(
            observed_at=observed_at,
            name=client.name,
            mac=client.mac,
            ip=client.ip,
            online=client.online,
            device_type=client.device_type,
            connection_type=client.connection_type,
            download_speed=client.download_speed,
            upload_speed=client.upload_speed,
            remain_time=client.remain_time,
            enable_priority=client.enable_priority,
            enable_internet=client.enable_internet,
        )
