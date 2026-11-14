"""Punto de entrada del backend de NEXUS Lite."""
import logging
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import FastAPI

from app.api import router
from app.map_config import load_map
from app.repository import MissionRepository, MongoMissionRepository
from app.service import FleetService
from app.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


def _mongo_repo() -> MissionRepository:
    return MongoMissionRepository(settings.mongo_url, settings.mongo_db)


def create_app(
    repository_factory: Callable[[], MissionRepository] = _mongo_repo,
    run_simulation: bool = True,
) -> FastAPI:
    """Los tests pasan un repositorio en memoria y desactivan el bucle."""

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.map = load_map(settings.map_file)
        app.state.service = FleetService(app.state.map, repository_factory())
        await app.state.service.start(run_loop=run_simulation)
        yield
        await app.state.service.stop()

    app = FastAPI(
        title="NEXUS Lite",
        version="0.2.0",
        description="Mini gestor de flota AMR: misiones, asignación y telemetría.",
        lifespan=lifespan,
    )

    @app.get("/health", tags=["sistema"])
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/map", tags=["mapa"])
    async def get_map():
        """Configuración del mapa: cuadrícula, estaciones y robots iniciales."""
        return app.state.map

    app.include_router(router)
    return app


app = create_app()
