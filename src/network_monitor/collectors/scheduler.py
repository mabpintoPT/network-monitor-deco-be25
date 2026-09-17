from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)


class PeriodicCollector:
    """Executa uma função de recolha periodicamente até ser cancelado."""

    def __init__(self, callback: Callable[[], Awaitable[None]], interval: int) -> None:
        if interval < 5:
            raise ValueError("O intervalo mínimo do collector é 5 segundos.")
        self.callback = callback
        self.interval = interval
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None and not self._task.done():
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="network-monitor-collector")

    async def stop(self) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self) -> None:
        while not self._stop.is_set():
            try:
                await self.callback()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Erro durante a recolha da rede")

            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                pass
