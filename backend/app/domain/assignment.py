"""B-02: asignación automática de misiones.

Regla del enunciado:
  - Se atiende primero la misión PENDING de mayor prioridad (1 = máxima) y,
    a igualdad, la más antigua.
  - Se asigna al robot libre (IDLE) más cercano a su origen con batería >= 30 %.

Distancia Manhattan, porque los robots se mueven por ejes (sin diagonales).
Empate de distancia: id de robot, para que el resultado sea determinista.

Es un algoritmo voraz (misión a misión). No busca el óptimo global de todas
las parejas: respeta la prioridad, que es lo que pide el enunciado.
"""
from typing import Callable, Iterable

from app.domain.models import Mission, MissionState, Robot, RobotState

Pos = tuple[int, int]


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def mission_order_key(m: Mission):
    return (m.priority, m.created_at)


def is_eligible(robot: Robot, min_battery: float) -> bool:
    return robot.state == RobotState.IDLE and robot.battery >= min_battery


def plan_assignments(
    missions: Iterable[Mission],
    robots: Iterable[Robot],
    origin_pos: Callable[[str], Pos],
    min_battery: float,
) -> list[tuple[Mission, Robot]]:
    """Devuelve las parejas (misión, robot) a asignar. No modifica nada."""
    free = [r for r in robots if is_eligible(r, min_battery)]
    pending = sorted((m for m in missions if m.state == MissionState.PENDING), key=mission_order_key)

    plan: list[tuple[Mission, Robot]] = []
    for mission in pending:
        if not free:
            break
        origin = origin_pos(mission.origin)
        best = min(free, key=lambda r: (manhattan(r.pos, origin), r.id))
        free.remove(best)
        plan.append((mission, best))
    return plan
