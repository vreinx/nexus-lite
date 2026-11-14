"""Punto de entrada del backend de NEXUS Lite."""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.map_config import load_map
from app.settings import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fase 1: solo cargamos y validamos el mapa. Mongo, Influx y el
    # simulador se enganchan aquí en las siguientes fases.
    app.state.map = load_map(settings.map_file)
    yield


app = FastAPI(
    title="NEXUS Lite",
    version="0.1.0",
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
