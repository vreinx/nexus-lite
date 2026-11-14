"""Tests de la API (B-01, B-07) con repositorio en memoria y sin bucle de simulación."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import InMemoryMissionRepository


@pytest.fixture
def client():
    app = create_app(InMemoryMissionRepository, run_simulation=False)
    with TestClient(app) as c:
        yield c


def crear(client, origin="P1", destination="D1", priority=2):
    return client.post("/api/v1/missions",
                       json={"origin": origin, "destination": destination, "priority": priority})


def test_crear_y_consultar_mision(client):
    r = crear(client, "P2", "D2", 1)
    assert r.status_code == 201
    body = r.json()
    assert body["state"] == "PENDING" and body["robot_id"] is None

    r = client.get(f"/api/v1/missions/{body['id']}")
    assert r.status_code == 200 and r.json()["origin"] == "P2"


@pytest.mark.parametrize("payload", [
    {"origin": "P1", "destination": "D1", "priority": 5},          # prioridad fuera de rango
    {"origin": "P1", "destination": "D1"},                          # falta prioridad
    {"origin": "D1", "destination": "D2", "priority": 1},           # origen no es de recogida
    {"origin": "P1", "destination": "P2", "priority": 1},           # destino no es de entrega
    {"origin": "P1", "destination": "D1", "priority": 1, "x": 1},   # campo desconocido
    {"origin": "P1", "destination": "D1", "priority": "alta"},      # tipo incorrecto
])
def test_crear_mision_invalida_422(client, payload):
    assert client.post("/api/v1/missions", json=payload).status_code == 422


def test_listar_con_filtro_por_estado(client):
    a = crear(client).json()["id"]
    crear(client)
    client.post(f"/api/v1/missions/{a}/cancel")

    todas = client.get("/api/v1/missions").json()
    pendientes = client.get("/api/v1/missions", params={"state": "PENDING"}).json()
    canceladas = client.get("/api/v1/missions", params={"state": "CANCELLED"}).json()
    assert len(todas) == 2 and len(pendientes) == 1 and len(canceladas) == 1
    assert canceladas[0]["id"] == a

    assert client.get("/api/v1/missions", params={"state": "NO_EXISTE"}).status_code == 422


def test_cancelar(client):
    mid = crear(client).json()["id"]
    r = client.post(f"/api/v1/missions/{mid}/cancel")
    assert r.status_code == 200 and r.json()["state"] == "CANCELLED"

    assert client.post(f"/api/v1/missions/{mid}/cancel").status_code == 409   # ya cancelada
    assert client.post("/api/v1/missions/no-existe/cancel").status_code == 404


def test_robots(client):
    robots = client.get("/api/v1/robots").json()
    assert [r["id"] for r in robots] == ["R1", "R2", "R3", "R4", "R5"]
    assert all(r["state"] == "IDLE" and r["battery"] == 100 for r in robots)

    assert client.get("/api/v1/robots/R3").json()["x"] == 10
    assert client.get("/api/v1/robots/R9").status_code == 404
    assert client.get("/api/v1/missions/no-existe").status_code == 404
