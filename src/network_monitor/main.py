from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from network_monitor.collectors.deco.client import DecoClient
from network_monitor.collectors.deco.collector import DecoCollector
from network_monitor.collectors.scheduler import PeriodicCollector
from network_monitor.database.database import Database
from network_monitor.database.repository import NetworkRepository
from network_monitor.services.devices import DeviceService
from network_monitor.services.presence import PresenceService
from network_monitor.services.traffic import TrafficService
from network_monitor.settings import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


class AppState:
    def __init__(self) -> None:
        self.db = Database(settings.database_url)
        self.repository = NetworkRepository(self.db)
        self.device_service = DeviceService(self.repository)
        self.presence_service = PresenceService(self.repository)
        self.traffic_service = TrafficService(self.repository)
        self.deco = DecoClient(
            host=settings.deco_host,
            username=settings.deco_username,
            password=settings.deco_password,
            timeout=settings.deco_timeout,
            verify_tls=settings.deco_verify_tls,
        )
        self.collector = DecoCollector(self.deco)
        self.scheduler: PeriodicCollector | None = None
        self.last_collection: str | None = None
        self.last_collection_count = 0
        self.last_collection_error: str | None = None
        self.last_traffic_collection_error: str | None = None
        self.last_traffic_count = 0
        self.collection_lock = asyncio.Lock()

    async def collect_once(self) -> None:
        async with self.collection_lock:
            try:
                bundle = await asyncio.to_thread(self.collector.collect_bundle)
                self.repository.record_collection(bundle.snapshots, observed_at=bundle.snapshots[0].observed_at if bundle.snapshots else datetime.now(timezone.utc))
                self.repository.record_traffic_samples(bundle.traffic)
                self.last_collection = datetime.now(timezone.utc).isoformat()
                self.last_collection_count = len(bundle.snapshots)
                self.last_collection_error = None
                self.last_traffic_collection_error = bundle.traffic_error
                self.last_traffic_count = len(bundle.traffic)
                logger.info(
                    "Recolha concluída: %d dispositivos, %d estatísticas de tráfego",
                    len(bundle.snapshots), len(bundle.traffic),
                )
            except Exception as exc:
                self.last_collection_error = str(exc)
                logger.exception("Falha na recolha")

    async def start(self) -> None:
        if settings.collector_enabled:
            self.scheduler = PeriodicCollector(self.collect_once, settings.collector_interval)
            await self.scheduler.start()
            logger.info("Collector ativo: intervalo=%ss", settings.collector_interval)
        else:
            logger.info("Collector desativado")

    async def stop(self) -> None:
        if self.scheduler:
            await self.scheduler.stop()
        self.deco.stok = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    state = AppState()
    app.state.network = state
    await state.start()
    yield
    await state.stop()


app = FastAPI(title="Network Monitor", version="1.4.0", lifespan=lifespan)

BASE = __import__("pathlib").Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE / "web" / "static"), name="static")


def state(request: Request) -> AppState:
    return request.app.state.network


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(BASE / "web" / "templates" / "index.html")


@app.get("/api/v1/health")
def health(request: Request):
    s = state(request)
    return {
        "status": "ok",
        "collector_enabled": settings.collector_enabled,
        "collector_interval": settings.collector_interval,
        "last_collection": s.last_collection,
        "last_collection_count": s.last_collection_count,
        "last_collection_error": s.last_collection_error,
        "last_traffic_collection_error": s.last_traffic_collection_error,
        "last_traffic_count": s.last_traffic_count,
        "database": str(s.db.path),
    }


@app.post("/api/v1/collector/run")
async def collector_run(request: Request):
    s = state(request)
    await s.collect_once()
    if s.last_collection_error:
        raise HTTPException(status_code=502, detail=s.last_collection_error)
    return {"ok": True, "count": s.last_collection_count, "timestamp": s.last_collection}


@app.get("/api/v1/stats")
def stats(request: Request):
    return state(request).repository.stats()


@app.get("/api/v1/devices")
def devices(request: Request):
    return state(request).device_service.list()


@app.get("/api/v1/devices/{mac}")
def device_detail(mac: str, request: Request):
    result = state(request).device_service.detail(mac)
    if result is None:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    return result


@app.get("/api/v1/devices/{mac}/observations")
def device_observations(mac: str, request: Request, limit: int = Query(500, ge=1, le=5000)):
    return state(request).repository.observations(mac, limit=limit)


@app.get("/api/v1/sessions")
def sessions(request: Request, mac: str | None = None, limit: int = Query(200, ge=1, le=2000)):
    return state(request).repository.sessions(mac=mac, limit=limit)


@app.get("/api/v1/traffic/{mac}")
def traffic(mac: str, request: Request, limit: int = Query(500, ge=1, le=5000)):
    return state(request).traffic_service.device_samples(mac, limit=limit)


@app.get("/api/v1/devices/{mac}/history")
def device_history(mac: str, request: Request, limit: int = Query(200, ge=1, le=2000)):
    result = state(request).device_service.detail(mac)
    if result is None:
        raise HTTPException(status_code=404, detail="Dispositivo não encontrado")
    result["history"] = state(request).repository.device_history(mac, limit=limit)
    return result
