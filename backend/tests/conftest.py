import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.domain.models import Mission
from app.domain.simulator import FleetSimulator
from app.map_config import MapConfig

MAP_FILE = Path(__file__).parent.parent / "config" / "map.json"
T0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)


def build_sim(robots: list[dict] | None = None, **sim_params) -> FleetSimulator:
    """Simulador con el mapa por defecto; permite cambiar robots y parámetros."""
    raw = json.loads(MAP_FILE.read_text(encoding="utf-8"))
    if robots is not None:
        raw["robots"] = robots
    raw["simulation"].update(sim_params)
    return FleetSimulator(MapConfig.model_validate(raw), clock=lambda: T0)


def mission(mid: str, origin="P1", dest="D1", priority=2, minutes=0) -> Mission:
    return Mission(id=mid, origin=origin, destination=dest, priority=priority,
                   created_at=T0 + timedelta(minutes=minutes))


@pytest.fixture
def make_sim():
    return build_sim


def login_as(client, username: str) -> str:
    """Inicia sesión por la API y deja el token en las cabeceras del cliente."""
    from app.settings import settings
    password = settings.operator_password if username == "operador" else settings.viewer_password
    token = client.post("/api/v1/auth/login",
                        json={"username": username, "password": password}).json()["token"]
    client.headers["Authorization"] = f"Bearer {token}"
    return token
