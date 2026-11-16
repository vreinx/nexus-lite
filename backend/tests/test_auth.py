"""Autenticación con dos roles: operador (actúa) y consulta (solo ve)."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.auth import Role, User, create_token
from app.main import create_app
from app.repository import InMemoryMissionRepository
from app.telemetry import InMemoryTelemetryStore
from tests.conftest import login_as


@pytest.fixture
def client():
    app = create_app(InMemoryMissionRepository, run_simulation=False,
                     telemetry_factory=InMemoryTelemetryStore)
    with TestClient(app) as c:
        yield c


def test_login(client):
    r = client.post("/api/v1/auth/login", json={"username": "operador", "password": "operador"})
    assert r.status_code == 200 and r.json()["role"] == "OPERATOR" and r.json()["token"]
    r = client.post("/api/v1/auth/login", json={"username": "consulta", "password": "consulta"})
    assert r.json()["role"] == "VIEWER"
    for user, pwd in (("operador", "mal"), ("nadie", "x")):
        assert client.post("/api/v1/auth/login", json={"username": user, "password": pwd}).status_code == 401


def test_sin_sesion_401(client):
    for url in ("/api/v1/robots", "/api/v1/missions", "/api/v1/map", "/api/v1/stations"):
        assert client.get(url).status_code == 401
    assert client.post("/api/v1/missions", json={"origin": "P1", "destination": "D1", "priority": 1}).status_code == 401
    assert client.get("/health").status_code == 200          # comprobación de vida, pública


def test_token_falso_o_caducado_401(client):
    client.headers["Authorization"] = "Bearer no-es-un-token"
    assert client.get("/api/v1/robots").status_code == 401
    viejo = create_token(User(username="operador", role=Role.OPERATOR, display_name="Operador"),
                         now=datetime.now(timezone.utc) - timedelta(days=2))
    client.headers["Authorization"] = f"Bearer {viejo}"
    assert client.get("/api/v1/robots").status_code == 401


def test_consulta_puede_ver_pero_no_actuar(client):
    login_as(client, "consulta")
    for url in ("/api/v1/robots", "/api/v1/missions", "/api/v1/map", "/api/v1/stations",
                "/api/v1/robots/R1/telemetry", "/api/v1/auth/me"):
        assert client.get(url).status_code == 200, url

    acciones = [
        ("post", "/api/v1/missions", {"origin": "P1", "destination": "D1", "priority": 1}),
        ("post", "/api/v1/missions/x/cancel", None),
        ("post", "/api/v1/missions/x/retry", None),
        ("post", "/api/v1/stations/P1/pallet", None),
        ("delete", "/api/v1/stations/P1/pallet", None),
        ("post", "/api/v1/robots/R1/error", None),
        ("post", "/api/v1/robots/R1/reset", None),
    ]
    for method, url, body in acciones:
        r = getattr(client, method)(url, **({"json": body} if body else {}))
        assert r.status_code == 403, (url, r.status_code)
        assert "solo permite ver" in r.json()["detail"]


def test_operador_puede_actuar(client):
    login_as(client, "operador")
    r = client.post("/api/v1/missions", json={"origin": "P1", "destination": "D1", "priority": 1})
    assert r.status_code == 201
    assert client.post("/api/v1/robots/R1/error").status_code == 200
    assert client.get("/api/v1/auth/me").json()["role"] == "OPERATOR"


def test_websocket_exige_sesion(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws") as ws:
            ws.receive_json()
    token = login_as(client, "consulta")                       # consulta también ve en vivo
    with client.websocket_connect(f"/ws?token={token}") as ws:
        assert ws.receive_json()["type"] == "snapshot"
