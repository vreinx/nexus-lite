"""Tráfico: dos robots nunca comparten celda y el menos prioritario cede el paso."""
import random

import pytest

from app.domain.models import MissionState, RobotState
from tests.conftest import build_sim, mission


def assert_no_collisions(sim):
    cells = [r.pos for r in sim.robots.values()]
    assert len(cells) == len(set(cells)), f"colisión: {sorted(cells)}"


def test_misma_celda_entra_el_mas_prioritario(make_sim):
    # R1 avanza por la fila 5 hacia la derecha y R2 baja por la columna 3:
    # los dos necesitan (3,5) en el mismo tick y no tienen otra opción.
    sim = make_sim(robots=[{"id": "R1", "x": 2, "y": 5}, {"id": "R2", "x": 3, "y": 4}])
    r1, r2 = sim.robots["R1"], sim.robots["R2"]
    alta, baja = mission("alta", priority=1), mission("baja", priority=3)
    sim.missions = {"alta": alta, "baja": baja}
    r1.state, r1.mission_id, r1.target = RobotState.TO_DROP, "baja", (9, 5)
    r2.state, r2.mission_id, r2.target = RobotState.TO_DROP, "alta", (3, 9)
    sim._resolve_traffic([r1, r2])
    assert r2.pos == (3, 5)          # prioridad 1 entra
    assert r1.pos == (2, 5) and r1.waiting
    assert_no_collisions(sim)


def test_a_igual_prioridad_pasa_la_mision_mas_antigua(make_sim):
    sim = make_sim(robots=[{"id": "R1", "x": 2, "y": 5}, {"id": "R2", "x": 3, "y": 4}])
    r1, r2 = sim.robots["R1"], sim.robots["R2"]
    vieja, nueva = mission("vieja", priority=2, minutes=0), mission("nueva", priority=2, minutes=5)
    sim.missions = {"vieja": vieja, "nueva": nueva}
    r1.state, r1.mission_id, r1.target = RobotState.TO_DROP, "vieja", (9, 5)
    r2.state, r2.mission_id, r2.target = RobotState.TO_DROP, "nueva", (3, 9)
    sim._resolve_traffic([r1, r2])
    assert r1.pos == (3, 5)          # la más antigua pasa
    assert r2.pos == (3, 4) and r2.waiting


def test_de_frente_el_menos_prioritario_se_aparta(make_sim):
    # En la misma fila, uno hacia la derecha y otro hacia la izquierda.
    sim = make_sim(robots=[{"id": "R1", "x": 2, "y": 5}, {"id": "R2", "x": 9, "y": 5}])
    r1, r2 = sim.robots["R1"], sim.robots["R2"]
    alta, baja = mission("alta", priority=1), mission("baja", priority=3)
    sim.missions = {"alta": alta, "baja": baja}
    r1.state, r1.mission_id, r1.target = RobotState.TO_DROP, "alta", (12, 5)
    r2.state, r2.mission_id, r2.target = RobotState.TO_DROP, "baja", (0, 5)

    apartado = False
    for _ in range(40):
        sim._resolve_traffic([r for r in (r1, r2) if r.pos != r.target])
        assert_no_collisions(sim)
        apartado |= r2.y != 5
        assert r1.y == 5              # el prioritario nunca se desvía
        if r1.pos == r1.target and r2.pos == r2.target:
            break
    assert apartado
    assert r1.pos == (12, 5) and r2.pos == (0, 5)


def test_robot_aparcado_se_aparta_y_vuelve_a_su_parking(make_sim):
    # R2 aparcado en PK3 (8,6), justo en la ruta de R1 por la fila 6.
    sim = make_sim(robots=[{"id": "R1", "x": 2, "y": 6}, {"id": "R2", "x": 8, "y": 6}])
    sim.add_mission(mission("m1", "P2", "D2"))   # para que R1 tenga misión
    r1, r2 = sim.robots["R1"], sim.robots["R2"]
    m = sim.missions["m1"]
    m.state, m.robot_id = MissionState.ASSIGNED, "R1"
    r1.state, r1.mission_id, r1.target = RobotState.TO_DROP, "m1", (19, 6)

    for _ in range(40):
        sim.tick()
        assert_no_collisions(sim)
    assert r1.pos == (19, 6) or r1.state != RobotState.TO_DROP
    assert r2.pos == (8, 6) and r2.target is None   # ha vuelto a PK3


@pytest.mark.parametrize("seed", [0, 1, 42])
def test_estres_sin_colisiones_y_todas_las_misiones_terminan(seed):
    """60 órdenes aleatorias. Un "operador" repone los palets de origen en
    cuanto se vacían y las órdenes se lanzan cuando son válidas (palet libre en
    origen y destino libre). Nunca dos robots en la misma celda, ningún robot
    sin batería y todas las órdenes terminan."""
    from app.domain.simulator import MissionError
    rng = random.Random(seed)
    sim = build_sim()
    picks, drops = ["P1", "P2", "P3", "P4"], ["D1", "D2"]
    specs = [(rng.choice(picks), rng.choice(drops), rng.randint(1, 3)) for _ in range(60)]
    created = 0

    for t in range(3000):
        for p in picks:
            if p not in sim.pallets:
                sim.declare_pallet(p)
        while created < len(specs):
            o, d, pr = specs[created]
            try:
                sim.add_mission(mission(f"m{created:02d}", o, d, priority=pr, minutes=created))
            except MissionError:
                break
            created += 1
        antes = {r.id: r.pos for r in sim.robots.values()}
        sim.tick()
        assert_no_collisions(sim)
        # Nadie entra en una casilla de entrega mientras tiene el palet anterior
        con_palet = {sim._station_pos(sid) for sid, left in sim.pallets.items() if left is not None}
        assert not [r.id for r in sim.robots.values() if r.pos in con_palet and antes[r.id] != r.pos]
        if created == len(specs) and all(m.state == MissionState.DONE for m in sim.missions.values()):
            break

    assert created == len(specs)
    estados = {m.state for m in sim.missions.values()}
    assert estados == {MissionState.DONE}, f"misiones sin terminar: {estados}"
    assert all(r.state != RobotState.ERROR for r in sim.robots.values())
