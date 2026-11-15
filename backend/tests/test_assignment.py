"""B-02: tests de la lógica de asignación (función pura)."""
from app.domain.assignment import plan_assignments
from app.domain.models import MissionState, Robot, RobotState
from tests.conftest import mission

POS = {"P1": (0, 1), "P2": (0, 4), "P4": (0, 10), "D1": (19, 3), "D2": (19, 8)}


def plan(missions, robots, min_battery=30):
    return [(m.id, r.id) for m, r in plan_assignments(missions, robots, POS.__getitem__, min_battery)]


def test_mayor_prioridad_primero():
    ms = [mission("baja", priority=3), mission("alta", priority=1), mission("media", priority=2)]
    robots = [Robot("R1", 5, 5)]
    assert plan(ms, robots) == [("alta", "R1")]


def test_a_igual_prioridad_la_mas_antigua():
    ms = [mission("nueva", priority=1, minutes=5), mission("vieja", priority=1, minutes=0)]
    assert plan(ms, [Robot("R1", 5, 5)]) == [("vieja", "R1")]


def test_robot_mas_cercano_al_origen():
    ms = [mission("m1", origin="P4")]          # P4 = (0,10)
    robots = [Robot("lejos", 19, 0), Robot("cerca", 2, 10), Robot("medio", 10, 10)]
    assert plan(ms, robots) == [("m1", "cerca")]


def test_empate_de_distancia_por_id():
    ms = [mission("m1", origin="P2")]          # P2 = (0,4)
    robots = [Robot("R2", 0, 6), Robot("R1", 0, 2)]
    assert plan(ms, robots) == [("m1", "R1")]


def test_excluye_bateria_baja_y_robots_ocupados():
    ms = [mission("m1")]
    robots = [
        Robot("sin_bateria", 0, 1, battery=29.5),
        Robot("ocupado", 0, 1, state=RobotState.TO_DROP),
        Robot("justo_30", 19, 11, battery=30),
    ]
    assert plan(ms, robots) == [("m1", "justo_30")]


def test_varias_misiones_varios_robots():
    ms = [mission("m_p4", origin="P4", priority=1), mission("m_p1", origin="P1", priority=2)]
    robots = [Robot("arriba", 0, 0), Robot("abajo", 0, 11)]
    # La prioritaria elige primero (P4 -> 'abajo'); la otra se queda con el resto.
    assert plan(ms, robots) == [("m_p4", "abajo"), ("m_p1", "arriba")]


def test_sin_robots_libres_no_asigna_y_solo_pending():
    ms = [mission("m1"), mission("hecha")]
    ms[1].state = MissionState.DONE
    assert plan(ms, []) == []
    assert plan(ms, [Robot("R1", 0, 0)]) == [("m1", "R1")]


def test_excluye_robot_sin_bateria_para_terminar_y_volver_a_cargar():
    from app.domain.assignment import plan_assignments
    ms = [mission("larga", origin="P1", dest="D1")]
    # Desde (19,11): 29 celdas a P1 + 21 a D1 + 13 a C1 (10,0) = 63 celdas = 31,5 %
    justo = Robot("justo", 19, 11, battery=35)
    sobrado = Robot("sobrado", 19, 11, battery=40)
    plan_ = plan_assignments(ms, [justo, sobrado], POS.__getitem__, 30,
                             charger=(10, 0), per_cell=0.5, reserve=5)
    assert [(m.id, r.id) for m, r in plan_] == [("larga", "sobrado")]
