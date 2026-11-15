"""Simulador de la flota. Lógica pura: cada llamada a tick() avanza 1 segundo.

Orden dentro de un tick:
  1. Robots que no se desplazan: cargar/descargar mercancía, cargar batería.
  2. Tráfico: los robots que se desplazan avanzan 1 celda por turnos de
     prioridad, sin coincidir nunca dos en la misma celda (ver sección Tráfico).
  3. B-03: los robots libres con batería baja se mandan a C1 (o a su cola).
  4. B-02: se asignan las misiones pendientes a los robots libres.
  5. Parkings: los robots libres sin destino van al parking libre más cercano.
     Siguen en IDLE mientras van, así que se les puede asignar una misión por
     el camino.

Ciclo de una misión:
  PENDING -> ASSIGNED (robot va a recoger) -> IN_PROGRESS (robot llega y empieza
  a cargar la mercancía) -> DONE (termina de descargar).
"""
from collections import deque
from datetime import datetime, timezone
from typing import Callable

from app.domain.assignment import manhattan, mission_cost, plan_assignments
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

# Ticks bloqueado por un robot que no puede moverse antes de rodearlo.
DETOUR_AFTER = 3
# Batería (%) que debe sobrar tras misión + vuelta a C1, para desvíos de tráfico.
BATTERY_RESERVE = 5.0


class MissionError(Exception):
    """Operación no permitida sobre una misión (se traduce a 409 en la API)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FleetSimulator:
    def __init__(self, cfg: MapConfig, clock: Callable[[], datetime] = _utcnow):
        self.cfg = cfg
        self.p = cfg.simulation
        self.clock = clock
        self.width, self.height = cfg.grid.width, cfg.grid.height

        self.robots: dict[str, Robot] = {
            r.id: Robot(id=r.id, x=r.x, y=r.y, battery=r.battery) for r in cfg.robots
        }
        self.missions: dict[str, Mission] = {}

        # B-03: C1 tiene una celda por plaza. charger_slots: robot -> plaza reservada.
        charger = cfg.charger
        self.charger_bays: list[Pos] = charger.cells
        self.charger_capacity = charger.capacity
        self.charger_queue_pos: Pos | None = (charger.queue.x, charger.queue.y) if charger.queue else None
        self.charger_slots: dict[str, Pos] = {}
        self.charger_queue: deque[str] = deque()

        self.parkings: list[tuple[str, Pos]] = [
            (s.id, (s.x, s.y)) for s in cfg.stations_of(StationType.PARKING)
        ]

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
            r.state, r.mission_id, r.target, r.waiting = RobotState.IDLE, None, None, False
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
        movers: list[Robot] = []
        for r in self.robots.values():
            if self._is_travelling(r):
                if r.pos == r.target:
                    self._arrive(r)
                else:
                    movers.append(r)
            else:
                self._step_in_place(r)

        self._resolve_traffic(movers)
        for r in movers:
            if r.state != RobotState.ERROR and r.target and r.pos == r.target:
                self._arrive(r)

        self._send_low_battery_to_charger()
        self._assign()
        self._send_idle_to_parking()

    def drain_changes(self) -> tuple[list[Robot], list[Mission]]:
        """Robots y misiones que han cambiado desde la última llamada."""
        robots = [self.robots[i] for i in sorted(self._dirty_robots)]
        missions = [self.missions[i] for i in sorted(self._dirty_missions)]
        self._dirty_robots.clear()
        self._dirty_missions.clear()
        return robots, missions

    # ------------------------------------------------------------- comportamiento
    @staticmethod
    def _is_travelling(r: Robot) -> bool:
        return r.target is not None and (
            r.state in MOVING or r.state == RobotState.IDLE
        )

    def _step_in_place(self, r: Robot) -> None:
        if r.state in (RobotState.LOADING, RobotState.UNLOADING):
            r.timer -= 1
            self._touch_robot(r)
            if r.timer <= 0:
                self._finish_handling(r)

        elif r.state == RobotState.CHARGING:
            r.battery = min(self.p.charge_target, r.battery + self.p.charge_per_second)
            self._touch_robot(r)
            if r.battery >= self.p.charge_target:
                r.state, r.target = RobotState.IDLE, None
                self.charger_slots.pop(r.id, None)

    def _arrive(self, r: Robot) -> None:
        r.waiting, r.blocked_ticks = False, 0
        if r.state == RobotState.IDLE:
            r.target = None  # aparcado
        elif r.state == RobotState.TO_PICKUP:
            r.state, r.timer = RobotState.LOADING, self.p.load_seconds
            m = self.missions[r.mission_id]
            m.state = MissionState.IN_PROGRESS
            self._touch_mission(m)
        elif r.state == RobotState.TO_DROP:
            r.state, r.timer = RobotState.UNLOADING, self.p.unload_seconds
        elif r.state == RobotState.TO_CHARGER and r.target in self.charger_bays:
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
        self.charger_slots.pop(r.id, None)
        if r.id in self.charger_queue:
            self.charger_queue.remove(r.id)
        r.state, r.mission_id, r.target, r.waiting = RobotState.ERROR, None, None, False
        self._touch_robot(r)

    # -------------------------------------------------------------------- Tráfico
    # Reglas (dos robots nunca comparten celda):
    #  - Cada tick se mueven por turnos, del más prioritario al menos:
    #      1º robots con misión: prioridad de la misión y, a igualdad, la más antigua
    #      2º robots que van a cargar      3º robots que van al parking
    #  - Cada robot intenta avanzar por su eje preferido (primero X, luego Y) o,
    #    si está ocupado, por el otro eje si también le acerca.
    #  - Si dos quieren la misma celda, entra el más prioritario y el otro se para.
    #  - Si un robot más prioritario necesita la celda donde está otro (de frente
    #    o porque está parado en su camino), el menos prioritario se aparta a una
    #    celda lateral libre y espera un tick: siempre cede el paso. Los robots
    #    aparcados también se apartan, y después vuelven a su parking.
    #  - Si lo bloquea un robot que no puede moverse (cargando, en C1, en error),
    #    espera DETOUR_AFTER ticks y lo rodea por un lateral.
    #  - Si la celda bloqueada es su propio destino (estación ocupada), espera.
    def _priority_key(self, r: Robot):
        if r.mission_id:
            m = self.missions[r.mission_id]
            return (0, m.priority, m.created_at.timestamp(), r.id)
        if r.state == RobotState.TO_CHARGER:
            return (1, 0, 0.0, r.id)
        return (2, 0, 0.0, r.id)

    @staticmethod
    def _preferred_steps(pos: Pos, target: Pos) -> list[Pos]:
        """Celdas vecinas que acercan al destino: primero por X y luego por Y."""
        (x, y), (tx, ty) = pos, target
        steps = []
        if x != tx:
            steps.append((x + (1 if tx > x else -1), y))
        if y != ty:
            steps.append((x, y + (1 if ty > y else -1)))
        return steps

    @staticmethod
    def _route(pos: Pos, target: Pos) -> set[Pos]:
        """Celdas de la ruta en L (primero X, luego Y) hasta el destino."""
        (x, y), (tx, ty) = pos, target
        cells = set()
        while x != tx:
            x += 1 if tx > x else -1
            cells.add((x, y))
        while y != ty:
            y += 1 if ty > y else -1
            cells.add((x, y))
        return cells

    def _can_make_way(self, r: Robot) -> bool:
        """Robot parado que puede apartarse si estorba."""
        if r.state == RobotState.IDLE:
            return r.target is None or r.pos == r.target
        return r.state == RobotState.TO_CHARGER and r.id in self.charger_queue and r.pos == r.target

    def _in_grid(self, c: Pos) -> bool:
        return 0 <= c[0] < self.width and 0 <= c[1] < self.height

    def _resolve_traffic(self, movers: list[Robot]) -> None:
        occupied: dict[Pos, Robot] = {r.pos: r for r in self.robots.values()}
        # Celda que necesita cada robot que se ha quedado bloqueado este tick.
        # Como se procesan por prioridad, quien aparece aquí siempre es más
        # prioritario que los que se procesan después.
        wanted_by: dict[Pos, Robot] = {}

        for r in sorted(movers, key=self._priority_key):
            was_waiting = r.waiting
            steps = self._preferred_steps(r.pos, r.target)

            if r.hold_ticks > 0:
                r.hold_ticks -= 1
            else:
                free = next((c for c in steps if c not in occupied), None)
                if free is not None:
                    self._move_to(r, free, occupied)
                    continue

            # No ha avanzado este tick.
            r.blocked_ticks += 1
            higher = wanted_by.get(r.pos)
            blocker = occupied.get(steps[0])
            if higher is not None:
                # Un robot más prioritario necesita mi celda: me aparto.
                if self._sidestep(r, occupied, avoid=self._route(higher.pos, higher.target)):
                    r.hold_ticks = 1
                    continue
            elif (r.hold_ticks == 0 and steps[0] != r.target and blocker is not None
                  and r.id not in self.charger_queue   # en la cola de C1 se espera, sin gastar batería
                  and not self._can_make_way(blocker) and not self._is_travelling(blocker)
                  and r.blocked_ticks >= DETOUR_AFTER):
                # Bloqueado por un robot que no se va a mover: lo rodeo.
                if self._sidestep(r, occupied, avoid={blocker.pos}):
                    continue

            if r.state != RobotState.ERROR:
                wanted_by[steps[0]] = r
                r.waiting = True
                if not was_waiting:
                    self._touch_robot(r)

        # Robots parados que estorban se apartan y luego vuelven: aparcados,
        # libres sin destino y los que esperan turno de carga (parking o cola).
        for pos, higher in list(wanted_by.items()):
            r = occupied.get(pos)
            if r is not None and self._can_make_way(r):
                if self._sidestep(r, occupied, avoid=self._route(higher.pos, higher.target)):
                    r.hold_ticks = 1

    def _move_to(self, r: Robot, cell: Pos, occupied: dict[Pos, Robot]) -> None:
        del occupied[r.pos]
        r.x, r.y = cell
        occupied[cell] = r
        r.blocked_ticks, r.waiting = 0, False
        r.battery = max(0.0, r.battery - self.p.battery_per_cell)
        self._touch_robot(r)
        if r.battery <= 0:
            self._fail_robot(r, "batería agotada en ruta")

    def _sidestep(self, r: Robot, occupied: dict[Pos, Robot], avoid: set[Pos]) -> bool:
        """Mueve el robot a una celda vecina libre. Prefiere las que no estén en
        la ruta del robot al que deja pasar y las que menos le alejan de su destino."""
        x, y = r.pos
        options = [c for c in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1))
                   if self._in_grid(c) and c not in occupied]
        if not options:
            return False
        goal = r.target or r.pos
        cell = min(options, key=lambda c: (c in avoid, manhattan(c, goal), c))
        self._move_to(r, cell, occupied)
        return True

    # ---------------------------------------------------------------------- B-03
    # Cola de carga (FIFO): robots con batería baja que esperan plaza en C1.
    #   - Si hay plaza libre, el primero de la cola va directo a ella.
    #   - Si no, el primero espera en la celda de cola de C1 (una sola plaza).
    #   - El resto espera en el parking libre más cercano (o donde esté si no hay).
    # Mientras esperan siguen en TO_CHARGER: no están IDLE, así que nunca se
    # les asigna una misión aunque estén parados en un parking.
    def _send_low_battery_to_charger(self) -> None:
        low = [
            r for r in self.robots.values()
            if r.state == RobotState.IDLE and r.battery < self.p.low_battery_threshold
        ]
        # Si varios bajan del umbral a la vez, primero el de menos batería.
        for r in sorted(low, key=lambda r: (r.battery, r.id)):
            self._send_to_charger(r)
        self._update_charger_queue()

    def _send_to_charger(self, r: Robot) -> None:
        r.state = RobotState.TO_CHARGER
        r.target = None
        self.charger_queue.append(r.id)
        self._touch_robot(r)

    def _update_charger_queue(self) -> None:
        # 1) Plazas libres para los primeros de la cola, en orden de llegada.
        while self.charger_queue:
            bay = self._free_bay(self.robots[self.charger_queue[0]].pos)
            if bay is None:
                break
            r = self.robots[self.charger_queue.popleft()]
            self.charger_slots[r.id] = bay
            self._retarget(r, bay)

        # 2) El primero que sigue esperando, a la celda de cola; el resto, a un parking.
        for i, rid in enumerate(self.charger_queue):
            r = self.robots[rid]
            if i == 0 and self.charger_queue_pos is not None:
                self._retarget(r, self.charger_queue_pos)
            elif r.target is None or r.target == self.charger_queue_pos:
                self._retarget(r, self._waiting_spot(r))

    def _waiting_spot(self, r: Robot) -> Pos:
        """Parking donde esperar turno de carga: el que hace más corto el trayecto
        total (robot -> parking -> C1). Si no le llega la batería, espera donde está."""
        charger = self.charger_queue_pos or self.charger_bays[0]
        taken = self._taken_parkings(exclude=r)
        options = [ppos for _, ppos in self.parkings if ppos not in taken]
        if not options:
            return r.pos
        cost = lambda c: manhattan(r.pos, c) + manhattan(c, charger)
        best = min(options, key=lambda c: (cost(c), c))
        if r.battery - cost(best) * self.p.battery_per_cell < 1.0:
            return r.pos
        return best

    def _retarget(self, r: Robot, target: Pos) -> None:
        if r.target != target:
            r.target = target
            r.blocked_ticks = 0
            self._touch_robot(r)

    def _free_bay(self, near: Pos) -> Pos | None:
        taken = set(self.charger_slots.values())
        # Una plaza con un robot parado encima (p. ej. en ERROR) no sirve.
        blocked = {r.pos for r in self.robots.values() if r.id not in self.charger_slots
                   and not self._is_travelling(r)}
        free = [b for b in self.charger_bays if b not in taken and b not in blocked]
        return min(free, key=lambda b: (manhattan(near, b), b)) if free else None

    # ------------------------------------------------------------------ parkings
    def parking_at(self, pos: Pos) -> str | None:
        return next((pid for pid, ppos in self.parkings if ppos == pos), None)

    def _taken_parkings(self, exclude: Robot | None = None) -> set[Pos]:
        """Parkings ocupados (robot parado encima) o reservados (robot que va hacia él)."""
        cells = {ppos for _, ppos in self.parkings}
        taken = set()
        for r in self.robots.values():
            if r is exclude:
                continue
            if r.target in cells:
                taken.add(r.target)
            elif r.target is None and r.pos in cells:
                taken.add(r.pos)
        return taken

    def _send_idle_to_parking(self) -> None:
        if not self.parkings:
            return
        cells = {ppos for _, ppos in self.parkings}
        idle = sorted((r for r in self.robots.values() if r.state == RobotState.IDLE), key=lambda r: r.id)

        # Si el parking al que iba un robot libre se ha ocupado o reservado
        # entretanto (p. ej. por un robot que espera para cargar), busca otro.
        for r in idle:
            if r.target in cells and r.target in self._taken_parkings(exclude=r):
                r.target = None

        # Sin destino y fuera de un parking: al parking libre más cercano.
        for r in idle:
            if r.target is None and r.pos not in cells:
                taken = self._taken_parkings(exclude=r)
                free = [(pid, ppos) for pid, ppos in self.parkings if ppos not in taken]
                if not free:
                    return  # sin hueco: se quedan donde están y se reintenta el siguiente tick
                _, ppos = min(free, key=lambda p: (manhattan(r.pos, p[1]), p[0]))
                self._retarget(r, ppos)

    # ---------------------------------------------------------------------- B-02
    def _assign(self) -> None:
        plan = plan_assignments(
            self.missions.values(),
            self.robots.values(),
            self._station_pos,
            self.p.min_battery_to_assign,
            charger=self.charger_bays[0],
            per_cell=self.p.battery_per_cell,
            reserve=BATTERY_RESERVE,
        )
        for m, r in plan:
            m.state, m.robot_id = MissionState.ASSIGNED, r.id
            r.state, r.mission_id, r.target = RobotState.TO_PICKUP, m.id, self._station_pos(m.origin)
            r.blocked_ticks = 0
            self._touch_mission(m)
            self._touch_robot(r)

        # Si quedan misiones pendientes y un robot libre no tiene batería para
        # ninguna, va a cargar aunque no haya bajado del umbral: si no, se
        # quedaría parado para siempre entre el 20 % y lo que pide la misión.
        pending = [m for m in self.missions.values() if m.state == MissionState.PENDING]
        if not pending:
            return
        cheapest = {}
        for r in self.robots.values():
            if r.state != RobotState.IDLE or r.battery >= self.p.charge_target:
                continue
            mine = [m for m in pending if m.preferred_robot in (None, r.id)]
            if not mine:
                continue
            need = min(
                mission_cost(r.pos, self._station_pos(m.origin), self._station_pos(m.destination),
                             self.charger_bays[0], self.p.battery_per_cell)
                for m in mine
            ) + BATTERY_RESERVE
            if r.battery < max(need, self.p.min_battery_to_assign):
                cheapest[r.id] = r
        for r in sorted(cheapest.values(), key=lambda r: (r.battery, r.id)):
            self._send_to_charger(r)

    # ------------------------------------------------------------------- helpers
    def _station_pos(self, station_id: str) -> Pos:
        s = self.cfg.station(station_id)
        return (s.x, s.y)

    def _touch_robot(self, r: Robot) -> None:
        self._dirty_robots.add(r.id)

    def _touch_mission(self, m: Mission) -> None:
        m.updated_at = self.clock()
        self._dirty_missions.add(m.id)
