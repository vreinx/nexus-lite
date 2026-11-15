"""Traducción de los filtros del historial a consulta MongoDB."""
from datetime import datetime, timezone

from app.domain.models import MissionState
from app.repository import MissionFilter


def test_filtro_a_consulta_mongo():
    desde = datetime(2026, 11, 1, tzinfo=timezone.utc)
    q = MissionFilter(states=[MissionState.FAILED, MissionState.DONE], robot_id="R2",
                      origin="P1", priority=1, created_from=desde, id_prefix="ab.c").to_mongo()
    assert q == {
        "state": {"$in": ["FAILED", "DONE"]},
        "robot_id": "R2",
        "origin": "P1",
        "priority": 1,
        "created_at": {"$gte": desde},
        "_id": {"$regex": r"^ab\.c"},   # el prefijo se escapa: no se puede inyectar una regex
    }


def test_filtro_vacio_no_filtra():
    assert MissionFilter().to_mongo() == {}
