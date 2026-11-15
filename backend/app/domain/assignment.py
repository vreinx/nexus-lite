"""B-02: asignación automática de misiones.

Regla del enunciado:
  - Se atiende primero la misión PENDING de mayor prioridad (1 = máxima) y,
    a igualdad, la más antigua.
  - Se asigna al robot libre (IDLE) más cercano a su origen con batería >= 30 %.

Distancia Manhattan, porque los robots se mueven por ejes (sin diagonales).
Empate de distancia: id de robot, para que el resultado sea determinista.

Además del 30 % del enunciado, el robot debe tener batería suficiente para
ir al origen, llevar la carga al destino y volver al cargador, con un margen
(los desvíos por tráfico también gastan batería). Sin esto, un robot con un
30 % podía aceptar una misión larga y quedarse sin batería antes de cargar.

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


def mission_cost(robot_pos: Pos, origin: Pos, dest: Pos, charger: Pos, per_cell: float) -> float:
    """Batería (%) para ir al origen, al destino y volver al cargador."""
    cells = manhattan(robot_pos, origin) + manhattan(origin, dest) + manhattan(dest, charger)
    return cells * per_cell


def plan_assignments(
    missions: Iterable[Mission],
    robots: Iterable[Robot],
    station_pos: Callable[[str], Pos],
    min_battery: float,
    charger: Pos | None = None,
    per_cell: float = 0.0,
    reserve: float = 0.0,
) -> list[tuple[Mission, Robot]]:
    """Devuelve las parejas (misión, robot) a asignar. No modifica nada."""
    free = [r for r in robots if is_eligible(r, min_battery)]
    pending = sorted((m for m in missions if m.state == MissionState.PENDING), key=mission_order_key)

    plan: list[tuple[Mission, Robot]] = []
    for mission in pending:
        if not free:
            break
        origin, dest = station_pos(mission.origin), station_pos(mission.destination)
        capable = free
        if charger is not None:
            capable = [r for r in free
                       if r.battery - mission_cost(r.pos, origin, dest, charger, per_cell) >= reserve]
        if not capable:
            continue   # ningún robot libre llega con esta misión; se prueba la siguiente
        best = min(capable, key=lambda r: (manhattan(r.pos, origin), r.id))
        free.remove(best)
        plan.append((mission, best))
    return plan
