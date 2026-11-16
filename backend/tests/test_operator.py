"""Acciones de operador (forzar ERROR, rearmar, retirar palet) y rutas A*."""
from tests.conftest import login_as
import pytest
from fastapi.testclient import TestClient

from app.domain.models import MissionState, RobotState
from app.domain.pathfinding import astar
from app.domain.simulator import MissionError
from tests.conftest import mission


def run_until(sim, cond, max_ticks=300):
    for _ in range(max_ticks):
        sim.tick()
        if cond():
            return
    raise AssertionError("la condición no se cumplió")


# ------------------------------------------------------------------ A*
def test_astar_en_linea_recta_es_la_L_del_enunciado():
    assert astar((0, 0), (3, 2), 20, 12, set()) == [(1, 0), (2, 0), (3, 0), (3, 1), (3, 2)]


def test_astar_rodea_un_obstaculo():
    camino = astar((0, 5), (4, 5), 20, 12, {(2, 5)})
    assert (2, 5) not in camino and camino[-1] == (4, 5)
    assert len(camino) == 6          # 4 en recta + 2 de rodeo


def test_astar_sin_camino_y_destino_bloqueado():
    muro = {(1, y) for y in range(12)}
    assert astar((0, 0), (5, 0), 20, 12, muro) is None
    assert astar((0, 0), (2, 0), 20, 12, {(2, 0)}) == [(1, 0), (2, 0)]   # el destino sí se puede pisar


def test_robot_rodea_a_un_robot_averiado(make_sim):
    # R2 averiado en (5,4), justo en la fila por la que R1 iría a D1.
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 4}, {"id": "R2", "x": 5, "y": 4}])
    sim.force_error("R2")
    sim.add_mission(mission("m1", "P2", "D1"))
    r1 = sim.robots["R1"]
    run_until(sim, lambda: r1.state == RobotState.TO_DROP)
    sim.tick()
    assert r1.path and (5, 4) not in r1.path       # la ruta lo esquiva
    run_until(sim, lambda: sim.missions["m1"].state == MissionState.DONE)
    assert r1.blocked_ticks == 0


# ------------------------------------------------------------ forzar ERROR
def test_error_antes_de_recoger_reasigna_la_orden(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 3, "y": 1}, {"id": "R2", "x": 9, "y": 9}])
    sim.add_mission(mission("m1", "P1", "D1"))
    sim.tick()
    assert sim.missions["m1"].robot_id == "R1"
    sim.force_error("R1")
    m = sim.missions["m1"]
    assert m.state == MissionState.PENDING and "reasignada" in m.reason
    sim.tick()
    assert m.robot_id == "R2"                      # la coge otro robot


def test_error_con_el_palet_a_bordo_pausa_y_al_rearmar_termina_la_entrega(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 2}])
    sim.add_mission(mission("m1", "P1", "D1"))
    r, m = sim.robots["R1"], sim.missions["m1"]
    run_until(sim, lambda: r.state == RobotState.TO_DROP)
    for _ in range(3):
        sim.tick()
    sim.force_error("R1")

    # En pausa: el robot conserva la orden y el palet
    assert r.state == RobotState.ERROR and r.mission_id == "m1"
    assert m.state == MissionState.IN_PROGRESS and "en pausa" in m.reason
    assert sim.is_carrying(r)
    for _ in range(5):
        sim.tick()
    assert m.state == MissionState.IN_PROGRESS and r.state == RobotState.ERROR   # sigue parado
    with pytest.raises(MissionError):
        sim.force_error("R1")                      # ya está en ERROR

    # Al rearmar retoma la entrega y la termina (no va al parking)
    sim.reset_robot("R1")
    assert r.state == RobotState.TO_DROP
    run_until(sim, lambda: m.state == MissionState.DONE)
    assert r.pos == (19, 3) and "D1" in sim.pallets    # el palet llega a su destino


def test_rearmar_con_palet_y_poca_bateria_carga_y_despues_entrega(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 2}])
    sim.add_mission(mission("m1", "P1", "D1"))
    r, m = sim.robots["R1"], sim.missions["m1"]
    run_until(sim, lambda: r.state == RobotState.TO_DROP)
    sim.force_error("R1")
    r.battery = 3                                  # no le llega para entregar y volver a C1
    sim.reset_robot("R1")
    assert r.pos in sim.charger_bays and r.mission_id == "m1"
    run_until(sim, lambda: r.state == RobotState.CHARGING)
    assert sim.is_carrying(r)                      # carga con el palet encima
    run_until(sim, lambda: r.state == RobotState.TO_DROP, max_ticks=100)
    run_until(sim, lambda: m.state == MissionState.DONE)
    assert "D1" in sim.pallets


# ---------------------------------------------------------------- rearmar
def test_rearmar_con_bateria_vuelve_a_idle(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 3, "y": 3, "battery": 60}])
    sim.force_error("R1")
    sim.reset_robot("R1")
    assert sim.robots["R1"].state == RobotState.IDLE and sim.robots["R1"].pos == (3, 3)
    with pytest.raises(MissionError):
        sim.reset_robot("R1")                      # no está en ERROR


def test_rearmar_sin_bateria_lo_lleva_a_cargar(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 3, "y": 3, "battery": 0}])
    sim.force_error("R1")
    sim.reset_robot("R1")
    r = sim.robots["R1"]
    assert r.pos in sim.charger_bays
    sim.tick()
    sim.tick()
    assert r.state == RobotState.CHARGING and r.battery > 0


def test_rearmar_sin_bateria_y_sin_plaza_libre_falla(make_sim):
    sim = make_sim(robots=[
        {"id": "R1", "x": 3, "y": 3, "battery": 0},
        {"id": "R2", "x": 10, "y": 0, "battery": 50},
        {"id": "R3", "x": 12, "y": 0, "battery": 50},
    ])
    for rid in ("R2", "R3"):                       # dos robots averiados ocupando las plazas
        sim.force_error(rid)
    sim.force_error("R1")
    with pytest.raises(MissionError, match="no hay plaza libre"):
        sim.reset_robot("R1")


# ----------------------------------------------------------- retirar palet
def test_retirar_palet(make_sim):
    sim = make_sim()
    sim.remove_pallet("P1")
    assert "P1" not in sim.pallets
    with pytest.raises(MissionError, match="No hay palet"):
        sim.remove_pallet("P1")
    sim.add_mission(mission("m1", "P2", "D1"))
    with pytest.raises(MissionError, match="orden asignada"):
        sim.remove_pallet("P2")
    with pytest.raises(ValueError):
        sim.remove_pallet("D1")


# -------------------------------------------------------------------- API
@pytest.fixture
def client():
    from app.main import create_app
    from app.repository import InMemoryMissionRepository
    from app.telemetry import InMemoryTelemetryStore
    app = create_app(InMemoryMissionRepository, run_simulation=False,
                     telemetry_factory=InMemoryTelemetryStore)
    with TestClient(app) as c:
        login_as(c, "operador")
        yield c


def test_api_operador(client):
    r = client.post("/api/v1/robots/R1/error")
    assert r.status_code == 200 and r.json()["state"] == "ERROR"
    assert client.post("/api/v1/robots/R1/error").status_code == 409
    r = client.post("/api/v1/robots/R1/reset")
    assert r.status_code == 200 and r.json()["state"] == "IDLE"
    assert client.post("/api/v1/robots/R1/reset").status_code == 409
    assert client.post("/api/v1/robots/R9/error").status_code == 404

    assert client.delete("/api/v1/stations/P3/pallet").status_code == 200
    assert client.delete("/api/v1/stations/P3/pallet").status_code == 409
    assert client.delete("/api/v1/stations/D1/pallet").status_code == 422
