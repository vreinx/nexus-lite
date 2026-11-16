from tests.conftest import login_as
import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.main import create_app
from app.map_config import MapConfig, load_map
from app.repository import InMemoryMissionRepository
from app.telemetry import InMemoryTelemetryStore

MAP_FILE = Path(__file__).parent.parent / "config" / "map.json"


def _raw() -> dict:
    return json.loads(MAP_FILE.read_text(encoding="utf-8"))


def test_mapa_por_defecto_es_valido():
    m = load_map(MAP_FILE)
    assert (m.grid.width, m.grid.height) == (20, 12)
    assert len(m.robots) == 5
    assert m.charger.id == "C1" and m.charger.capacity == 2


def test_estacion_fuera_de_cuadricula_falla():
    raw = _raw()
    raw["stations"][0]["x"] = 20
    with pytest.raises(ValidationError, match="fuera de la cuadrícula"):
        MapConfig.model_validate(raw)


def test_id_repetido_falla():
    raw = _raw()
    raw["robots"][1]["id"] = raw["robots"][0]["id"]
    with pytest.raises(ValidationError, match="ids repetidos"):
        MapConfig.model_validate(raw)


def test_falta_cargador_falla():
    raw = copy.deepcopy(_raw())
    raw["stations"] = [s for s in raw["stations"] if s["type"] != "CHARGER"]
    with pytest.raises(ValidationError, match="CHARGER"):
        MapConfig.model_validate(raw)


def test_health_y_mapa():
    app = create_app(InMemoryMissionRepository, run_simulation=False, telemetry_factory=InMemoryTelemetryStore)
    with TestClient(app) as client:
        login_as(client, "operador")
        assert client.get("/health").json() == {"status": "ok"}
        body = client.get("/api/v1/map").json()
        assert len(body["stations"]) == 12


def test_dos_estaciones_en_la_misma_celda_falla():
    raw = _raw()
    raw["stations"][1]["x"], raw["stations"][1]["y"] = raw["stations"][0]["x"], raw["stations"][0]["y"]
    with pytest.raises(ValidationError, match="misma celda"):
        MapConfig.model_validate(raw)


def test_parkings_son_opcionales():
    raw = _raw()
    raw["stations"] = [s for s in raw["stations"] if s["type"] != "PARKING"]
    assert MapConfig.model_validate(raw)
