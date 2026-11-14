"""B-05: persistencia de misiones.

Dos implementaciones con la misma interfaz:
  - MongoMissionRepository: la real (MongoDB).
  - InMemoryMissionRepository: para los tests, sin necesidad de levantar Mongo.
"""
from dataclasses import asdict, replace
from typing import Protocol

from pymongo import AsyncMongoClient, ReplaceOne

from app.domain.models import ACTIVE_MISSION_STATES, Mission, MissionState


class MissionRepository(Protocol):
    async def init(self) -> None: ...
    async def save_many(self, missions: list[Mission]) -> None: ...
    async def get(self, mission_id: str) -> Mission | None: ...
    async def find(self, state: MissionState | None = None, limit: int = 100) -> list[Mission]: ...
    async def list_active(self) -> list[Mission]: ...
    async def close(self) -> None: ...


def to_doc(m: Mission) -> dict:
    doc = asdict(m)
    doc["_id"] = doc.pop("id")
    doc["state"] = m.state.value
    return doc


def from_doc(doc: dict) -> Mission:
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    doc["state"] = MissionState(doc["state"])
    return Mission(**doc)


class MongoMissionRepository:
    def __init__(self, url: str, db: str):
        # tz_aware: las fechas vuelven con zona horaria (UTC), igual que se guardan
        self._client = AsyncMongoClient(url, tz_aware=True)
        self._col = self._client[db]["missions"]

    async def init(self) -> None:
        await self._col.create_index([("state", 1), ("created_at", -1)])

    async def save_many(self, missions: list[Mission]) -> None:
        if not missions:
            return
        ops = [ReplaceOne({"_id": m.id}, to_doc(m), upsert=True) for m in missions]
        await self._col.bulk_write(ops, ordered=False)

    async def get(self, mission_id: str) -> Mission | None:
        doc = await self._col.find_one({"_id": mission_id})
        return from_doc(doc) if doc else None

    async def find(self, state: MissionState | None = None, limit: int = 100) -> list[Mission]:
        query = {"state": state.value} if state else {}
        cursor = self._col.find(query).sort("created_at", -1).limit(limit)
        return [from_doc(d) async for d in cursor]

    async def list_active(self) -> list[Mission]:
        query = {"state": {"$in": [s.value for s in ACTIVE_MISSION_STATES]}}
        return [from_doc(d) async for d in self._col.find(query)]

    async def close(self) -> None:
        await self._client.close()


class InMemoryMissionRepository:
    """Guarda copias, para simular que lo persistido no cambia por referencia."""

    def __init__(self, missions: list[Mission] | None = None):
        self._data: dict[str, Mission] = {m.id: replace(m) for m in missions or []}

    async def init(self) -> None:
        pass

    async def save_many(self, missions: list[Mission]) -> None:
        for m in missions:
            self._data[m.id] = replace(m)

    async def get(self, mission_id: str) -> Mission | None:
        m = self._data.get(mission_id)
        return replace(m) if m else None

    async def find(self, state: MissionState | None = None, limit: int = 100) -> list[Mission]:
        ms = [m for m in self._data.values() if state is None or m.state == state]
        ms.sort(key=lambda m: m.created_at, reverse=True)
        return [replace(m) for m in ms[:limit]]

    async def list_active(self) -> list[Mission]:
        return [replace(m) for m in self._data.values() if m.state in ACTIVE_MISSION_STATES]

    async def close(self) -> None:
        pass
