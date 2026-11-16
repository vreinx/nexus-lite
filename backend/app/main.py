"""Punto de entrada del backend de NEXUS Lite."""
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect, status

from app.api import auth_router, router
from app.auth import decode_token, require_user
from app.map_config import load_map
from app.realtime import ConnectionManager, encode
from app.repository import MissionRepository, MongoMissionRepository
from app.service import FleetService
from app.telemetry import InfluxTelemetryStore, TelemetryStore
from app.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _mongo_repo() -> MissionRepository:
    return MongoMissionRepository(settings.mongo_url, settings.mongo_db)


def _influx() -> TelemetryStore:
    return InfluxTelemetryStore(settings.influx_url, settings.influx_token,
                                settings.influx_org, settings.influx_bucket)


def create_app(
    repository_factory: Callable[[], MissionRepository] = _mongo_repo,
    run_simulation: bool = True,
    telemetry_factory: Callable[[], TelemetryStore] | None = _influx,
) -> FastAPI:
    """Los tests pasan un repositorio en memoria y desactivan el bucle."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.map = load_map(settings.map_file)
        telemetry = telemetry_factory() if telemetry_factory else None
        app.state.service = FleetService(app.state.map, repository_factory(), telemetry)
        app.state.service.notify = app.state.ws_clients.broadcast
        await app.state.service.start(run_loop=run_simulation)
        yield
        await app.state.service.stop()

    app = FastAPI(
        title="NEXUS Lite",
        version="0.3.0",
        description="Mini gestor de flota AMR: misiones, asignación y telemetría.",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["sistema"])
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/map", tags=["mapa"], dependencies=[Depends(require_user)])
    async def get_map():
        """Configuración del mapa: cuadrícula, estaciones y robots iniciales."""
        return app.state.map

    app.state.ws_clients = ConnectionManager()

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket):
        """B-04: snapshot al conectar y después solo los cambios.
        Requiere sesión: ?token=<token> (operador o consulta)."""
        if decode_token(ws.query_params.get("token", "")) is None:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)   # sin sesión: se rechaza
            return
        await ws.accept()
        service: FleetService = app.state.service
        # Con el candado: entre el snapshot y el alta no se cuela ningún update.
        async with service.lock:
            missions = await service.repo.find(limit=100)
            await ws.send_text(encode("snapshot", service.list_robots(), missions, service.stations()))
            app.state.ws_clients.add(ws)
        try:
            while True:
                await ws.receive_text()   # el cliente no envía nada; esperamos al cierre
        except WebSocketDisconnect:
            pass
        finally:
            app.state.ws_clients.remove(ws)

    app.include_router(auth_router)
    app.include_router(router)
    return app


app = create_app()
