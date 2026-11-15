"""Capa de servicio: une el simulador (dominio) con la persistencia.

- Un bucle asyncio llama a step() cada tick_seconds.
- Un asyncio.Lock evita que un tick y una petición de la API modifiquen el
  simulador o escriban en Mongo a la vez (y que una escritura antigua pise
  a una más reciente).
"""
import asyncio
import logging
import uuid
from dataclasses import replace
from datetime import datetime, timezone
from typing import Awaitable, Callable

from app.domain.models import Mission, MissionState, Robot
from app.domain.simulator import FleetSimulator, MissionError
from app.map_config import MapConfig
from app.repository import MissionFilter, MissionRepository
from app.telemetry import TelemetryStore

log = logging.getLogger("nexus.service")

Notifier = Callable[[list[Robot], list[Mission]], Awaitable[None]]

TELEMETRY_TIMEOUT_S = 2.0


class RepositoryUnavailable(Exception):
    """No se pudo guardar en base de datos (se traduce a 503 en la API)."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class FleetService:
    def __init__(self, cfg: MapConfig, repo: MissionRepository,
                 telemetry: TelemetryStore | None = None,
                 clock: Callable[[], datetime] = _utcnow):
        self.sim = FleetSimulator(cfg, clock)
        self.repo = repo
        self.telemetry = telemetry
        self._telemetry_ok = True
        self.clock = clock
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        # B-04: se llama con lo que cambia (lo engancha main.py al WebSocket).
        # Va dentro del candado para que los mensajes salgan en orden.
        self.notify: Notifier | None = None

    @property
    def lock(self) -> asyncio.Lock:
        return self._lock

    async def _notify(self, robots: list[Robot], missions: list[Mission]) -> None:
        if self.notify:
            try:
                await self.notify(robots, missions)
            except Exception:
                log.exception("Error notificando cambios en tiempo real")

    # ------------------------------------------------------------ ciclo de vida
    async def start(self, run_loop: bool = True) -> None:
        await self.repo.init()
        await self.restore()
        if run_loop:
            self._task = asyncio.create_task(self._loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await self.repo.close()
        if self.telemetry:
            await self.telemetry.close()

    async def restore(self) -> None:
        """B-06: recupera el estado tras un reinicio.

        Robots: vuelven a la posición, batería y estado guardados en Mongo
        (ver FleetSimulator.restore_robots).
        Misiones: las ASSIGNED e IN_PROGRESS vuelven a PENDING y se reasignan;
        ninguna se pierde. Como el robot sigue donde estaba, lo normal es que
        la vuelva a coger él (es el más cercano). En una planta real habría que
        reconciliar con lo que reporta cada robot (p. ej. si lleva la carga).
        """
        restored_robots = self.sim.restore_robots(await self.repo.load_robots())
        robots, _ = self.sim.drain_changes()
        await self.repo.save_robots(robots)
        log.info("Reinicio: %d robots restaurados desde la base de datos", len(restored_robots))

        active = sorted(await self.repo.list_active(), key=lambda m: m.created_at)
        invalid: list[Mission] = []
        for m in active:
            if m.state != MissionState.PENDING:
                m.state, m.robot_id = MissionState.PENDING, None
                m.reason = "reencolada tras reinicio del backend"
            try:
                self.sim.add_mission(m)
            except ValueError as e:
                # p. ej. el mapa cambió y la estación ya no existe
                m.state, m.reason, m.updated_at = MissionState.FAILED, f"no válida con el mapa actual: {e}", self.clock()
                invalid.append(m)
        _, restored = self.sim.drain_changes()
        await self.repo.save_many(restored + invalid)
        log.info("Reinicio: %d misiones recuperadas, %d no válidas", len(restored), len(invalid))

    async def _loop(self) -> None:
        loop = asyncio.get_running_loop()
        period = self.sim.p.tick_seconds
        next_t = loop.time()
        while True:
            next_t += period
            try:
                await self.step()
            except Exception:
                log.exception("Error en el tick del simulador")
            await asyncio.sleep(max(0.0, next_t - loop.time()))

    async def step(self) -> tuple[list[Robot], list[Mission]]:
        """Un tick del simulador + persistencia de lo que ha cambiado."""
        async with self._lock:
            self.sim.tick()
            robots, missions = self.sim.drain_changes()
            await self._persist(missions)
            await self._persist_robots(robots)
            await self._notify(robots, missions)
            # Copia del estado de todos los robots para la telemetría
            snapshot = [replace(r) for r in self.sim.robots.values()]
            ts = self.clock()
        # B-05: fuera del candado, para que InfluxDB lento no frene el simulador
        await self._write_telemetry(snapshot, ts)
        return robots, missions

    async def _write_telemetry(self, robots: list[Robot], ts: datetime) -> None:
        if not self.telemetry:
            return
        try:
            await asyncio.wait_for(self.telemetry.write(robots, ts), TELEMETRY_TIMEOUT_S)
            if not self._telemetry_ok:
                log.info("Telemetría recuperada")
            self._telemetry_ok = True
        except Exception:
            # Se pierde ese punto, pero la simulación sigue. Se avisa una sola vez.
            if self._telemetry_ok:
                log.exception("No se pudo escribir la telemetría en InfluxDB")
            self._telemetry_ok = False

    async def _persist_robots(self, robots: list[Robot]) -> None:
        try:
            await self.repo.save_robots(robots)
        except Exception:
            # Si Mongo falla, se reintenta en el siguiente tick.
            log.exception("No se pudo guardar el estado de %d robots; se reintentará", len(robots))
            self.sim.mark_robots_dirty(r.id for r in robots)

    async def _persist(self, missions: list[Mission]) -> None:
        try:
            await self.repo.save_many(missions)
        except Exception:
            # Si Mongo falla, se reintenta en el siguiente tick.
            log.exception("No se pudieron guardar %d misiones; se reintentará", len(missions))
            self.sim.mark_missions_dirty(m.id for m in missions)

    # ---------------------------------------------------------------- misiones
    async def create_mission(self, origin: str, destination: str, priority: int) -> Mission:
        m = Mission(id=str(uuid.uuid4()), origin=origin, destination=destination,
                    priority=priority, created_at=self.clock())
        return await self._add_and_save(m)

    async def retry_mission(self, mission_id: str, robot_id: str | None = None) -> Mission:
        """Reenvía una misión FAILED o CANCELLED como misión nueva enlazada a la
        original (la original queda intacta, para la trazabilidad)."""
        original = await self.repo.get(mission_id)
        if original is None:
            raise KeyError(mission_id)
        if original.state not in (MissionState.FAILED, MissionState.CANCELLED):
            raise MissionError(f"solo se reenvían misiones FAILED o CANCELLED (está {original.state.value})")
        if robot_id is not None and robot_id not in self.sim.robots:
            raise ValueError(f"el robot '{robot_id}' no existe")
        m = Mission(id=str(uuid.uuid4()), origin=original.origin, destination=original.destination,
                    priority=original.priority, created_at=self.clock(),
                    retry_of=original.id, preferred_robot=robot_id)
        return await self._add_and_save(m)

    async def _add_and_save(self, m: Mission) -> Mission:
        async with self._lock:
            self.sim.add_mission(m)   # ValueError si no es válida -> 422
            try:
                # Se responde 201 solo cuando ya está guardada: no se pierde.
                await self.repo.save_many([m])
            except Exception as e:
                self.sim.remove_mission(m.id)
                raise RepositoryUnavailable("no se pudo guardar la misión") from e
            await self._notify([], [m])
        return m

    async def cancel_mission(self, mission_id: str) -> Mission:
        async with self._lock:
            try:
                m = self.sim.cancel_mission(mission_id)
            except KeyError:
                # No está en el simulador: o no existe, o terminó antes de un reinicio
                stored = await self.repo.get(mission_id)
                if stored is None:
                    raise
                raise MissionError(f"no se puede cancelar una misión en estado {stored.state.value}")
            await self._persist([m])
            # El robot liberado (si lo había) se notifica en el siguiente tick.
            await self._notify([], [m])
        return m

    async def get_mission(self, mission_id: str) -> Mission | None:
        return await self.repo.get(mission_id)

    async def list_missions(self, flt: MissionFilter, limit: int, offset: int = 0) -> tuple[list[Mission], int]:
        return await self.repo.find(flt, limit, offset), await self.repo.count(flt)

    # ------------------------------------------------------------------ robots
    def list_robots(self) -> list[Robot]:
        return list(self.sim.robots.values())

    def get_robot(self, robot_id: str) -> Robot | None:
        return self.sim.robots.get(robot_id)
