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
