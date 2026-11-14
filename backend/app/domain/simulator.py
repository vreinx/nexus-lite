"""Simulador de la flota. Lógica pura: cada llamada a tick() avanza 1 segundo.

Orden dentro de un tick:
  1. Cada robot avanza según su estado (moverse, cargar/descargar, cargar batería).
  2. B-03: los robots libres con batería baja se mandan a C1 (o a su cola).
  3. B-02: se asignan las misiones pendientes a los robots libres.

Ciclo de una misión:
  PENDING -> ASSIGNED (robot va a recoger) -> IN_PROGRESS (robot llega y empieza
  a cargar la mercancía) -> DONE (termina de descargar).
"""
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from app.domain.assignment import plan_assignments
from app.domain.models import (
    PRIORITY_MAX,
    PRIORITY_MIN,
    Mission,
    MissionState,
    Robot,
    RobotState,
)
from app.map_config import MapConfig, StationType

Pos = tuple[int, int]
MOVING = {RobotState.TO_PICKUP, RobotState.TO_DROP, RobotState.TO_CHARGER}


class MissionError(Exception):
    """Operación no permitida sobre una misión (se traduce a 409 en la API)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FleetSimulator:
    def __init__(self, cfg: MapConfig, clock: Callable[[], datetime] = _utcnow):
        self.cfg = cfg
        self.p = cfg.simulation
        self.clock = clock

        self.robots: dict[str, Robot] = {
            r.id: Robot(id=r.id, x=r.x, y=r.y, battery=r.battery) for r in cfg.robots
        }
        self.missions: dict[str, Mission] = {}

        # B-03: plazas de C1 ocupadas (robots cargando o yendo a cargar) y cola FIFO
        charger = cfg.charger
        self.charger_pos: Pos = (charger.x, charger.y)
        self.charger_capacity = charger.capacity
        self.charger_queue_pos: Pos | None = (charger.queue.x, charger.queue.y) if charger.queue else None
        self.charger_slots: set[str] = set()
        self.charger_queue: deque[str] = deque()

        self._dirty_robots: set[str] = set()
        self._dirty_missions: set[str] = set()

    # ------------------------------------------------------------------ misiones
    def add_mission(self, m: Mission) -> None:
        origin = self.cfg.station(m.origin)
        dest = self.cfg.station(m.destination)
        if origin is None or origin.type != StationType.PICKUP:
            raise ValueError(f"origen '{m.origin}' no es una estación de recogida")
        if dest is None or dest.type != StationType.DROP:
            raise ValueError(f"destino '{m.destination}' no es una estación de entrega")
        if not PRIORITY_MIN <= m.priority <= PRIORITY_MAX:
            raise ValueError(f"prioridad debe estar entre {PRIORITY_MIN} y {PRIORITY_MAX}")
        if m.id in self.missions:
            raise MissionError(f"la misión {m.id} ya existe")
        self.missions[m.id] = m
        self._touch_mission(m)

    def remove_mission(self, mission_id: str) -> None:
        """Deshace un add_mission (si no se pudo guardar en base de datos)."""
        self.missions.pop(mission_id, None)
        self._dirty_missions.discard(mission_id)

    def mark_missions_dirty(self, mission_ids) -> None:
        """Vuelve a marcar misiones para guardarlas (si falló la escritura)."""
        self._dirty_missions.update(i for i in mission_ids if i in self.missions)

    def cancel_mission(self, mission_id: str) -> Mission:
        m = self.missions.get(mission_id)
        if m is None:
            raise KeyError(mission_id)

        if m.state == MissionState.PENDING:
            pass
        elif m.state == MissionState.ASSIGNED:
            # El robot aún no ha recogido nada: se libera y queda donde está.
            r = self.robots[m.robot_id]
            r.state, r.mission_id, r.target = RobotState.IDLE, None, None
            self._touch_robot(r)
        elif m.state == MissionState.IN_PROGRESS:
            # El robot ya lleva la mercancía: cancelar la dejaría "en el aire".
            raise MissionError("no se puede cancelar: el robot ya ha recogido la carga")
        else:
            raise MissionError(f"no se puede cancelar una misión en estado {m.state.value}")

        m.state, m.reason = MissionState.CANCELLED, "cancelada por el usuario"
        self._touch_mission(m)
        return m

    # ---------------------------------------------------------------------- tick
    def tick(self) -> None:
        for r in self.robots.values():
            self._step(r)
        self._send_low_battery_to_charger()
        self._assign()

    def drain_changes(self) -> tuple[list[Robot], list[Mission]]:
        """Robots y misiones que han cambiado desde la última llamada."""
        robots = [self.robots[i] for i in sorted(self._dirty_robots)]
        missions = [self.missions[i] for i in sorted(self._dirty_missions)]
        self._dirty_robots.clear()
        self._dirty_missions.clear()
        return robots, missions

    # ------------------------------------------------------------- comportamiento
    def _step(self, r: Robot) -> None:
        if r.state in MOVING:
            if r.pos != r.target:
                self._move(r)
                if r.state == RobotState.ERROR:
                    return
            if r.pos == r.target:
                self._arrive(r)

        elif r.state in (RobotState.LOADING, RobotState.UNLOADING):
            r.timer -= 1
            self._touch_robot(r)
            if r.timer <= 0:
                self._finish_handling(r)

        elif r.state == RobotState.CHARGING:
            r.battery = min(self.p.charge_target, r.battery + self.p.charge_per_second)
            self._touch_robot(r)
            if r.battery >= self.p.charge_target:
                r.state, r.target = RobotState.IDLE, None
                self.charger_slots.discard(r.id)
                self._admit_from_queue()

    def _move(self, r: Robot) -> None:
        """1 celda en línea recta por ejes: primero X, luego Y."""
        tx, ty = r.target
        if r.x != tx:
            r.x += 1 if tx > r.x else -1
        else:
            r.y += 1 if ty > r.y else -1
        r.battery = max(0.0, r.battery - self.p.battery_per_cell)
        self._touch_robot(r)
        if r.battery <= 0:
            self._fail_robot(r, "batería agotada en ruta")

    def _arrive(self, r: Robot) -> None:
        if r.state == RobotState.TO_PICKUP:
            r.state, r.timer = RobotState.LOADING, self.p.load_seconds
            m = self.missions[r.mission_id]
            m.state = MissionState.IN_PROGRESS
            self._touch_mission(m)
        elif r.state == RobotState.TO_DROP:
            r.state, r.timer = RobotState.UNLOADING, self.p.unload_seconds
        elif r.state == RobotState.TO_CHARGER and r.target == self.charger_pos:
            r.state = RobotState.CHARGING
        else:
            return  # en la celda de cola de C1, esperando plaza
        self._touch_robot(r)

    def _finish_handling(self, r: Robot) -> None:
        m = self.missions[r.mission_id]
        if r.state == RobotState.LOADING:
            r.state, r.target = RobotState.TO_DROP, self._station_pos(m.destination)
        else:  # UNLOADING
            m.state = MissionState.DONE
            self._touch_mission(m)
            r.state, r.mission_id, r.target = RobotState.IDLE, None, None
        self._touch_robot(r)

    def _fail_robot(self, r: Robot, reason: str) -> None:
        if r.mission_id:
            m = self.missions[r.mission_id]
            m.state, m.reason = MissionState.FAILED, reason
            self._touch_mission(m)
        self.charger_slots.discard(r.id)
        if r.id in self.charger_queue:
            self.charger_queue.remove(r.id)
        r.state, r.mission_id, r.target = RobotState.ERROR, None, None
        self._touch_robot(r)
        self._admit_from_queue()

    # ---------------------------------------------------------------------- B-03
    def _send_low_battery_to_charger(self) -> None:
        low = [
            r for r in self.robots.values()
            if r.state == RobotState.IDLE and r.battery < self.p.low_battery_threshold
        ]
        # Si varios bajan del umbral a la vez, primero el de menos batería.
        for r in sorted(low, key=lambda r: (r.battery, r.id)):
            r.state = RobotState.TO_CHARGER
            if len(self.charger_slots) < self.charger_capacity:
                self.charger_slots.add(r.id)
                r.target = self.charger_pos
            else:
                # C1 llena: a la celda de espera, por orden de llegada (FIFO).
                self.charger_queue.append(r.id)
                r.target = self.charger_queue_pos or r.pos
            self._touch_robot(r)

    def _admit_from_queue(self) -> None:
        while self.charger_queue and len(self.charger_slots) < self.charger_capacity:
            r = self.robots[self.charger_queue.popleft()]
            self.charger_slots.add(r.id)
            r.target = self.charger_pos
            self._touch_robot(r)

    # ---------------------------------------------------------------------- B-02
    def _assign(self) -> None:
        plan = plan_assignments(
            self.missions.values(),
            self.robots.values(),
            self._station_pos,
            self.p.min_battery_to_assign,
        )
        for m, r in plan:
            m.state, m.robot_id = MissionState.ASSIGNED, r.id
            r.state, r.mission_id, r.target = RobotState.TO_PICKUP, m.id, self._station_pos(m.origin)
            self._touch_mission(m)
            self._touch_robot(r)

    # ------------------------------------------------------------------- helpers
    def _station_pos(self, station_id: str) -> Pos:
        s = self.cfg.station(station_id)
        return (s.x, s.y)

    def _touch_robot(self, r: Robot) -> None:
        self._dirty_robots.add(r.id)

    def _touch_mission(self, m: Mission) -> None:
        m.updated_at = self.clock()
        self._dirty_missions.add(m.id)
