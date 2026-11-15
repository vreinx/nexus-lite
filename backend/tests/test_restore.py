"""B-06: qué pasa con las misiones cuando el backend se reinicia."""
import asyncio

from app.domain.models import MissionState
from app.repository import InMemoryMissionRepository
from app.service import FleetService
from tests.conftest import build_sim, mission


def _mision(mid, state, origin="P1", minutes=0):
    m = mission(mid, origin=origin, minutes=minutes)
    m.state = state
    if state in (MissionState.ASSIGNED, MissionState.IN_PROGRESS):
        m.robot_id = "R1"
    return m


def test_reinicio_reencola_misiones_activas_y_no_pierde_ninguna():
    repo = InMemoryMissionRepository([
        _mision("pendiente", MissionState.PENDING, minutes=0),
        _mision("asignada", MissionState.ASSIGNED, minutes=1),
        _mision("en_curso", MissionState.IN_PROGRESS, minutes=2),
        _mision("hecha", MissionState.DONE, minutes=3),
        _mision("mapa_viejo", MissionState.PENDING, origin="P9", minutes=4),
    ])
    service = FleetService(build_sim().cfg, repo)

    async def scenario():
        await service.start(run_loop=False)
        return {m.id: m for m in await repo.find(limit=500)}

    stored = asyncio.run(scenario())

    for mid in ("pendiente", "asignada", "en_curso"):
        assert stored[mid].state == MissionState.PENDING
        assert stored[mid].robot_id is None
        assert mid in service.sim.missions
    assert stored["asignada"].reason == "reencolada tras reinicio del backend"

    assert stored["hecha"].state == MissionState.DONE           # las terminadas no se tocan
    assert "hecha" not in service.sim.missions

    assert stored["mapa_viejo"].state == MissionState.FAILED    # estación que ya no existe
    assert "mapa actual" in stored["mapa_viejo"].reason


def test_tras_reiniciar_se_reasignan():
    repo = InMemoryMissionRepository([_mision("en_curso", MissionState.IN_PROGRESS)])
    service = FleetService(build_sim().cfg, repo)

    async def scenario():
        await service.start(run_loop=False)
        await service.step()
        return await repo.get("en_curso")

    assert asyncio.run(scenario()).state == MissionState.ASSIGNED


def test_cada_tick_escribe_telemetria_de_todos_los_robots():
    from app.telemetry import InMemoryTelemetryStore
    telemetry = InMemoryTelemetryStore()
    service = FleetService(build_sim().cfg, InMemoryMissionRepository(), telemetry)

    async def scenario():
        await service.start(run_loop=False)
        await service.step()
        await service.step()

    asyncio.run(scenario())
    assert len(telemetry.points) == 2 * 5
    assert {p["robot_id"] for p in telemetry.points} == {"R1", "R2", "R3", "R4", "R5"}


def test_si_influx_falla_la_simulacion_sigue():
    class Rota:
        async def write(self, robots, ts): raise ConnectionError("influx caído")
        async def history(self, *a): return []
        async def close(self): pass

    service = FleetService(build_sim().cfg, InMemoryMissionRepository(), Rota())

    async def scenario():
        await service.start(run_loop=False)
        await service.create_mission("P1", "D1", 1)
        await service.step()
        return list(service.sim.missions.values())[0]

    assert asyncio.run(scenario()).state == MissionState.ASSIGNED


# ------------------------------------------------- estado de robots al reiniciar
def _run(service, coro_fn):
    async def scenario():
        await service.start(run_loop=False)
        return await coro_fn()
    return asyncio.run(scenario())


def test_reinicio_conserva_posicion_y_bateria_de_los_robots():
    repo = InMemoryMissionRepository()           # la "base de datos" sobrevive al reinicio
    cfg = build_sim().cfg

    antes = FleetService(cfg, repo)
    async def trabajar():
        await antes.create_mission("P1", "D1", 1)
        for _ in range(15):
            await antes.step()
        return {r.id: (r.pos, r.battery) for r in antes.sim.robots.values()}
    estado = _run(antes, trabajar)
    assert any(b < 100 for _, b in estado.values())        # alguien ha gastado batería

    despues = FleetService(cfg, repo)                       # "reinicio" del backend
    async def nada():
        return {r.id: (r.pos, r.battery) for r in despues.sim.robots.values()}
    assert _run(despues, nada) == estado


def test_reinicio_robot_en_error_sigue_en_error_y_el_que_cargaba_sigue_cargando():
    from app.domain.models import RobotState
    repo = InMemoryMissionRepository()
    repo.robots = {
        "R1": {"_id": "R1", "x": 3, "y": 3, "battery": 0.0, "state": "ERROR"},
        "R2": {"_id": "R2", "x": 10, "y": 0, "battery": 40.0, "state": "CHARGING"},   # plaza de C1
        "R3": {"_id": "R3", "x": 50, "y": 50, "battery": 70.0, "state": "IDLE"},      # fuera del mapa
    }
    service = FleetService(build_sim().cfg, repo)

    async def dos_ticks():
        await service.step()      # R2 "llega" a su plaza -> CHARGING
        await service.step()      # y empieza a sumar batería
        return service.sim.robots

    robots = _run(service, dos_ticks)
    assert robots["R1"].state == RobotState.ERROR and robots["R1"].pos == (3, 3)
    assert robots["R2"].state == RobotState.CHARGING and robots["R2"].battery > 40
    assert robots["R3"].pos == (8, 6) and robots["R3"].battery == 100   # posición de map.json
