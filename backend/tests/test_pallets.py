"""Palets: solo se mueve lo que existe y solo se deja donde hay sitio."""
import pytest

from app.domain.models import MissionState, RobotState
from app.domain.simulator import MissionError
from tests.conftest import mission


def run_until(sim, cond, max_ticks=300):
    for _ in range(max_ticks):
        sim.tick()
        if cond():
            return
    raise AssertionError("la condición no se cumplió")


def test_al_arrancar_los_origenes_tienen_palet(make_sim):
    sim = make_sim()
    assert set(sim.pallets) == {"P1", "P2", "P3", "P4"}


def test_origen_vacio_no_hay_nada_que_mover(make_sim):
    sim = make_sim()
    del sim.pallets["P1"]
    with pytest.raises(MissionError, match="No hay nada que mover en la posición P1"):
        sim.add_mission(mission("m1", "P1", "D1"))


def test_palet_ya_asignado_a_otra_orden(make_sim):
    sim = make_sim()
    sim.add_mission(mission("m1", "P1", "D1"))
    with pytest.raises(MissionError, match="ya tiene una orden asignada"):
        sim.add_mission(mission("m2", "P1", "D2"))


def test_cancelar_libera_el_palet_para_otra_orden(make_sim):
    sim = make_sim()
    sim.add_mission(mission("m1", "P1", "D1"))
    sim.cancel_mission("m1")
    sim.add_mission(mission("m2", "P1", "D2"))   # el palet sigue en P1 y vuelve a estar libre
    assert "P1" in sim.pallets


def test_ciclo_del_palet_origen_robot_destino(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 2}], drop_clear_seconds=2)
    sim.add_mission(mission("m1", "P1", "D1"))
    r = sim.robots["R1"]

    run_until(sim, lambda: r.state == RobotState.LOADING)
    assert "P1" in sim.pallets                    # mientras carga, sigue en el origen
    run_until(sim, lambda: r.state == RobotState.TO_DROP)
    assert "P1" not in sim.pallets                # ya va encima del robot

    run_until(sim, lambda: sim.missions["m1"].state == MissionState.DONE)
    assert sim.pallets["D1"] == 2                 # entregado: ocupa el destino 2 s
    with pytest.raises(MissionError, match="El destino D1 está ocupado"):
        sim.add_mission(mission("m2", "P2", "D1"))

    sim.tick()
    assert sim.pallets["D1"] == 1
    sim.tick()
    assert "D1" not in sim.pallets                # retirado
    sim.add_mission(mission("m2", "P2", "D1"))    # ya se puede


def test_robot_espera_si_el_destino_sigue_ocupado(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 18, "y": 3}], drop_clear_seconds=5)
    sim.add_mission(mission("m1", "P2", "D1"))
    m, r = sim.missions["m1"], sim.robots["R1"]
    m.state, m.robot_id = MissionState.IN_PROGRESS, "R1"
    r.state, r.mission_id, r.target = RobotState.TO_DROP, "m1", (19, 3)
    del sim.pallets["P2"]
    sim.pallets["D1"] = 3                         # palet de una entrega anterior

    sim.tick()                                    # llega a D1
    sim.tick()
    assert r.state == RobotState.TO_DROP and r.waiting
    run_until(sim, lambda: r.state == RobotState.UNLOADING)
    assert "D1" not in sim.pallets or sim.pallets["D1"] is not None


def test_declarar_palet(make_sim):
    sim = make_sim()
    del sim.pallets["P3"]
    sim.declare_pallet("P3")
    assert "P3" in sim.pallets
    with pytest.raises(MissionError, match="Ya hay un palet"):
        sim.declare_pallet("P3")
    with pytest.raises(ValueError):
        sim.declare_pallet("D1")                  # solo en estaciones de recogida
    with pytest.raises(KeyError):
        sim.declare_pallet("PX")


# ------------------------------------------------------------------------ API
@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import create_app
    from app.repository import InMemoryMissionRepository
    from app.telemetry import InMemoryTelemetryStore
    app = create_app(InMemoryMissionRepository, run_simulation=False,
                     telemetry_factory=InMemoryTelemetryStore)
    with TestClient(app) as c:
        yield c


def test_api_palets(client):
    st = {s["id"]: s for s in client.get("/api/v1/stations").json()}
    assert st["P1"]["pallet"] and not st["D1"]["pallet"]

    assert client.post("/api/v1/stations/P1/pallet").status_code == 409   # ya tiene
    assert client.post("/api/v1/stations/D1/pallet").status_code == 422   # no es origen
    assert client.post("/api/v1/stations/ZZ/pallet").status_code == 404

    mid = client.post("/api/v1/missions", json={"origin": "P1", "destination": "D1", "priority": 1}).json()["id"]
    st = {s["id"]: s for s in client.get("/api/v1/stations").json()}
    assert st["P1"]["reserved_by"] == mid

    r = client.post("/api/v1/missions", json={"origin": "P1", "destination": "D2", "priority": 1})
    assert r.status_code == 409 and "ya tiene una orden" in r.json()["detail"]


def test_api_origen_vacio_y_declarar(client):
    service = client.app.state.service
    del service.sim.pallets["P2"]
    r = client.post("/api/v1/missions", json={"origin": "P2", "destination": "D1", "priority": 2})
    assert r.status_code == 409 and r.json()["detail"] == "No hay nada que mover en la posición P2"

    r = client.post("/api/v1/stations/P2/pallet")
    assert r.status_code == 201 and r.json()["pallet"] is True
    assert client.post("/api/v1/missions", json={"origin": "P2", "destination": "D1", "priority": 2}).status_code == 201


def test_palets_sobreviven_al_reinicio():
    import asyncio
    from app.repository import InMemoryMissionRepository
    from app.service import FleetService
    from tests.conftest import build_sim

    repo = InMemoryMissionRepository()
    repo.stations = {"P1": False, "P2": True}
    service = FleetService(build_sim().cfg, repo)
    asyncio.run(service.start(run_loop=False))
    assert "P1" not in service.sim.pallets and "P2" in service.sim.pallets
