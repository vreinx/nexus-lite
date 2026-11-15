"""Tests de la API (B-01, B-07) con repositorio en memoria y sin bucle de simulación."""
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repository import InMemoryMissionRepository
from app.telemetry import InMemoryTelemetryStore


@pytest.fixture
def client():
    app = create_app(InMemoryMissionRepository, run_simulation=False, telemetry_factory=InMemoryTelemetryStore)
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

    assert client.get("/api/v1/robots/R3").json()["x"] == 8
    assert client.get("/api/v1/robots/R9").status_code == 404
    assert client.get("/api/v1/missions/no-existe").status_code == 404


def test_websocket_snapshot_y_updates(client):
    mid = crear(client, "P3", "D2", 1).json()["id"]
    with client.websocket_connect("/ws") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot"
        assert len(snap["robots"]) == 5
        assert [m["id"] for m in snap["missions"]] == [mid]

        # Crear otra misión se notifica al momento
        otra = crear(client, "P1", "D1", 2).json()["id"]
        upd = ws.receive_json()
        assert upd["type"] == "update" and upd["missions"][0]["id"] == otra

        client.post(f"/api/v1/missions/{otra}/cancel")
        upd = ws.receive_json()
        assert upd["missions"][0]["state"] == "CANCELLED"


def test_telemetria_de_robot(client):
    service = client.app.state.service
    # Simulamos dos ticks a mano (el bucle está desactivado en los tests)
    client.portal.call(service.step)
    client.portal.call(service.step)
    puntos = client.get("/api/v1/robots/R1/telemetry").json()
    assert len(puntos) == 2
    assert set(puntos[0]) == {"time", "x", "y", "battery", "state"}
    assert client.get("/api/v1/robots/R9/telemetry").status_code == 404
    assert client.get("/api/v1/robots/R1/telemetry", params={"minutes": 0}).status_code == 422


# ---------------------------------------------------------------- historial
def test_historial_filtros_y_paginacion(client):
    ids = {}
    for o, d, p in [("P1", "D1", 1), ("P2", "D2", 2), ("P1", "D2", 3), ("P3", "D1", 1)]:
        ids[(o, d, p)] = crear(client, o, d, p).json()["id"]
    client.post(f"/api/v1/missions/{ids[('P1', 'D2', 3)]}/cancel")

    def get(**params):
        r = client.get("/api/v1/missions", params=params)
        assert r.status_code == 200
        return r.json(), int(r.headers["X-Total-Count"])

    assert get(origin="P1")[1] == 2
    assert get(destination="D1", priority=1)[1] == 2
    assert get(state=["PENDING", "CANCELLED"])[1] == 4
    assert get(state="CANCELLED")[0][0]["origin"] == "P1"
    assert get(id_prefix=ids[("P2", "D2", 2)][:8])[0][0]["destination"] == "D2"

    pagina1, total = get(limit=3, offset=0)
    pagina2, _ = get(limit=3, offset=3)
    assert total == 4 and len(pagina1) == 3 and len(pagina2) == 1
    assert {m["id"] for m in pagina1 + pagina2} == set(ids.values())

    assert client.get("/api/v1/missions", params={"priority": 7}).status_code == 422
    assert client.get("/api/v1/missions", params={
        "created_from": "2030-01-02T00:00:00Z", "created_to": "2030-01-01T00:00:00Z"}).status_code == 422


def test_reenviar_mision_cancelada(client):
    original = crear(client, "P2", "D1", 1).json()["id"]
    assert client.post(f"/api/v1/missions/{original}/retry").status_code == 409   # aún PENDING
    client.post(f"/api/v1/missions/{original}/cancel")

    r = client.post(f"/api/v1/missions/{original}/retry", json={"robot_id": "R3"})
    assert r.status_code == 201
    nueva = r.json()
    assert nueva["retry_of"] == original and nueva["preferred_robot"] == "R3"
    assert nueva["state"] == "PENDING" and (nueva["origin"], nueva["destination"]) == ("P2", "D1")
    assert client.get(f"/api/v1/missions/{original}").json()["state"] == "CANCELLED"   # intacta

    assert client.post(f"/api/v1/missions/{original}/retry", json={"robot_id": "R9"}).status_code == 422
    assert client.post("/api/v1/missions/no-existe/retry").status_code == 404


def test_historial_por_robot_y_estado(client):
    service = client.app.state.service
    for o in ("P1", "P2", "P3"):
        crear(client, o, "D1", 1)
    client.portal.call(service.step)          # se asignan a robots
    asignadas = client.get("/api/v1/missions", params={"state": "ASSIGNED"}).json()
    robot = asignadas[0]["robot_id"]

    r = client.get("/api/v1/missions", params={"robot_id": robot, "state": ["ASSIGNED", "DONE"]})
    assert r.headers["X-Total-Count"] == "1"
    assert r.json()[0]["robot_id"] == robot
    r = client.get("/api/v1/missions", params={"robot_id": robot, "state": "DONE"})
    assert r.headers["X-Total-Count"] == "0"
