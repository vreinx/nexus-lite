"""Tests del simulador: ciclo de misión, carga de batería (B-03) y cancelación."""
import pytest

from app.domain.models import MissionState, RobotState
from app.domain.simulator import MissionError
from tests.conftest import mission


def run_until(sim, cond, max_ticks=500):
    for i in range(1, max_ticks + 1):
        sim.tick()
        if cond():
            return i
    raise AssertionError("la condición no se cumplió")


def test_ciclo_completo_de_mision(make_sim):
    # R1 a 2 celdas de P1 (0,1). P1 -> D1 (19,3) son 21 celdas.
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 3}])
    sim.add_mission(mission("m1", "P1", "D1"))
    r, m = sim.robots["R1"], sim.missions["m1"]

    estados = []
    ticks = 0
    while m.state != MissionState.DONE:
        sim.tick()
        ticks += 1
        if not estados or estados[-1] != (r.state, m.state):
            estados.append((r.state, m.state))
        assert ticks < 100

    assert [e[0] for e in estados] == [
        RobotState.TO_PICKUP, RobotState.LOADING, RobotState.TO_DROP,
        RobotState.UNLOADING, RobotState.IDLE,
    ]
    assert [e[1] for e in estados] == [
        MissionState.ASSIGNED, MissionState.IN_PROGRESS, MissionState.IN_PROGRESS,
        MissionState.IN_PROGRESS, MissionState.DONE,
    ]
    # 1 tick de asignación + 2 celdas + 3 s carga + 21 celdas + 3 s descarga = 30
    assert ticks == 30
    assert r.pos == (19, 3)
    assert r.battery == pytest.approx(100 - 23 * 0.5)


def test_bateria_baja_va_a_cargar_y_vuelve_a_idle(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 10, "y": 3, "battery": 15}])
    r = sim.robots["R1"]

    sim.tick()
    assert r.state == RobotState.TO_CHARGER and r.target == (10, 0)

    run_until(sim, lambda: r.state == RobotState.CHARGING)
    assert r.pos == (10, 0) and r.battery == pytest.approx(15 - 3 * 0.5)

    run_until(sim, lambda: r.state == RobotState.IDLE)
    assert r.battery == 100 and not sim.charger_slots


def test_robot_con_poca_bateria_no_recibe_misiones(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 1, "battery": 25}])
    sim.add_mission(mission("m1"))
    sim.tick()
    assert sim.missions["m1"].state == MissionState.PENDING
    assert sim.robots["R1"].state == RobotState.IDLE   # 25 % >= 20 %: ni carga ni misión


def test_c1_llena_cola_fifo(make_sim):
    sim = make_sim(robots=[
        {"id": "R1", "x": 9,  "y": 2, "battery": 10},
        {"id": "R2", "x": 11, "y": 2, "battery": 12},
        {"id": "R3", "x": 10, "y": 4, "battery": 15},
    ])
    sim.tick()
    # Los dos con menos batería ocupan C1; el tercero va a la celda de espera.
    assert sim.charger_slots == {"R1", "R2"}
    assert list(sim.charger_queue) == ["R3"]
    assert sim.robots["R3"].target == (10, 1)

    max_cargando = 0
    def r3_cargando():
        nonlocal max_cargando
        cargando = sum(r.state == RobotState.CHARGING for r in sim.robots.values())
        max_cargando = max(max_cargando, cargando)
        return sim.robots["R3"].state == RobotState.CHARGING

    run_until(sim, r3_cargando)
    assert max_cargando <= 2
    assert RobotState.IDLE in (sim.robots["R1"].state, sim.robots["R2"].state)


def test_cancelar_pending_y_assigned(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 10, "y": 11}])
    sim.add_mission(mission("m1", priority=1))
    sim.add_mission(mission("m2", priority=3))
    sim.tick()   # m1 -> ASSIGNED a R1, m2 sigue PENDING

    assert sim.cancel_mission("m2").state == MissionState.CANCELLED
    assert sim.cancel_mission("m1").state == MissionState.CANCELLED
    assert sim.robots["R1"].state == RobotState.IDLE
    assert sim.robots["R1"].mission_id is None


def test_no_se_cancela_in_progress_ni_terminada(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 1}])
    sim.add_mission(mission("m1"))
    run_until(sim, lambda: sim.missions["m1"].state == MissionState.IN_PROGRESS)
    with pytest.raises(MissionError):
        sim.cancel_mission("m1")

    sim.add_mission(mission("m2"))
    sim.cancel_mission("m2")
    with pytest.raises(MissionError):
        sim.cancel_mission("m2")
    with pytest.raises(KeyError):
        sim.cancel_mission("no-existe")


@pytest.mark.parametrize("origin,dest,priority", [
    ("D1", "D2", 2),   # origen no es de recogida
    ("P1", "P2", 2),   # destino no es de entrega
    ("P1", "D1", 0),   # prioridad fuera de rango
    ("PX", "D1", 2),   # estación inexistente
])
def test_validacion_de_mision(make_sim, origin, dest, priority):
    with pytest.raises(ValueError):
        make_sim().add_mission(mission("m1", origin, dest, priority))


def test_bateria_agotada_en_ruta_robot_error_y_mision_failed(make_sim):
    # Consumo exagerado para forzar que se quede sin batería en ruta.
    sim = make_sim(robots=[{"id": "R1", "x": 19, "y": 11, "battery": 30}], battery_per_cell=5)
    sim.add_mission(mission("m1"))
    run_until(sim, lambda: sim.robots["R1"].state == RobotState.ERROR)
    assert sim.missions["m1"].state == MissionState.FAILED
    assert sim.robots["R1"].battery == 0


def test_drain_changes_devuelve_solo_lo_cambiado(make_sim):
    # R2 aparcado en PK1: no se mueve, no debe aparecer como cambiado
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 1}, {"id": "R2", "x": 6, "y": 11}])
    sim.drain_changes()
    sim.add_mission(mission("m1"))
    sim.tick()
    robots, missions = sim.drain_changes()
    assert [r.id for r in robots] == ["R1"]
    assert [m.id for m in missions] == ["m1"]
    assert sim.drain_changes() == ([], [])


# ------------------------------------------------------------------ parkings
def test_al_terminar_va_al_parking_libre_mas_cercano(make_sim):
    # R1 hace P4 (0,10) -> D2 (19,8). El parking más cercano a D2 es PK5 (14,11).
    sim = make_sim(robots=[{"id": "R1", "x": 0, "y": 10}])
    sim.add_mission(mission("m1", "P4", "D2"))
    r = sim.robots["R1"]
    run_until(sim, lambda: sim.missions["m1"].state == MissionState.DONE)
    assert r.state == RobotState.IDLE

    sim.tick()
    assert r.target == (14, 11)
    run_until(sim, lambda: r.target is None)
    assert r.pos == (14, 11) and r.state == RobotState.IDLE
    assert sim.parking_at(r.pos) == "PK5"


def test_no_comparten_parking(make_sim):
    # Los dos fuera de parking y cerca de PK5: uno a PK5 y el otro al siguiente.
    sim = make_sim(robots=[{"id": "R1", "x": 14, "y": 8}, {"id": "R2", "x": 15, "y": 8}])
    sim.tick()
    targets = {sim.robots["R1"].target, sim.robots["R2"].target}
    assert targets == {(14, 11), (12, 11)}


def test_parking_ocupado_no_se_elige(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 14, "y": 11}, {"id": "R2", "x": 14, "y": 8}])
    sim.tick()
    assert sim.robots["R1"].target is None          # ya aparcado en PK5
    assert sim.robots["R2"].target == (12, 11)       # PK5 ocupado -> PK4


def test_camino_del_parking_se_le_puede_asignar_mision(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 3, "y": 5}])
    sim.tick()
    r = sim.robots["R1"]
    assert r.state == RobotState.IDLE and r.target == (6, 11)

    sim.add_mission(mission("m1", "P2", "D1"))
    sim.tick()
    assert r.state == RobotState.TO_PICKUP and r.target == (0, 4)


def test_sin_parkings_libres_se_queda_quieto(make_sim):
    robots = [{"id": f"R{i}", "x": x, "y": 11} for i, x in enumerate([6, 8, 10, 12, 14], 1)]
    robots.append({"id": "R6", "x": 3, "y": 3})
    sim = make_sim(robots=robots)
    sim.tick()
    assert sim.robots["R6"].target is None and sim.robots["R6"].pos == (3, 3)


def test_bateria_baja_va_a_cargar_antes_que_al_parking(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 3, "y": 5, "battery": 15}])
    sim.tick()
    assert sim.robots["R1"].state == RobotState.TO_CHARGER
