from __future__ import annotations

from abc import ABC, abstractmethod

from network_monitor.domain.models import DeviceSnapshot


class Collector(ABC):
    """Interface comum para qualquer fonte de dados de rede."""

    @abstractmethod
    def collect(self) -> list[DeviceSnapshot]:
        raise NotImplementedError
