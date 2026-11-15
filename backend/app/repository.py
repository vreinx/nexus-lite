"""B-05: persistencia de misiones y del estado actual de los robots.

El estado actual de cada robot (posición, batería, estado) se guarda en Mongo
para que un reinicio del backend no "teletransporte" los robots ni les cargue
la batería. El histórico de posición y batería va aparte, en InfluxDB.

Dos implementaciones con la misma interfaz:
  - MongoMissionRepository: la real (MongoDB).
  - InMemoryMissionRepository: para los tests, sin necesidad de levantar Mongo.
"""
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime
from typing import Protocol

from pymongo import AsyncMongoClient, ReplaceOne

from app.domain.models import ACTIVE_MISSION_STATES, Mission, MissionState, Robot


def robot_doc(r: Robot) -> dict:
    return {"_id": r.id, "x": r.x, "y": r.y, "battery": r.battery, "state": r.state.value}


@dataclass
class MissionFilter:
    """Filtros del historial. Los campos a None no filtran."""
    states: list[MissionState] | None = None
    robot_id: str | None = None
    origin: str | None = None
    destination: str | None = None
    priority: int | None = None
    created_from: datetime | None = None
    created_to: datetime | None = None
    id_prefix: str | None = None

    def matches(self, m: Mission) -> bool:
        return ((not self.states or m.state in self.states)
                and (self.robot_id is None or m.robot_id == self.robot_id)
                and (self.origin is None or m.origin == self.origin)
                and (self.destination is None or m.destination == self.destination)
                and (self.priority is None or m.priority == self.priority)
                and (self.created_from is None or m.created_at >= self.created_from)
                and (self.created_to is None or m.created_at <= self.created_to)
                and (self.id_prefix is None or m.id.startswith(self.id_prefix)))

    def to_mongo(self) -> dict:
        q: dict = {}
        if self.states:
            q["state"] = {"$in": [s.value for s in self.states]}
        for field in ("robot_id", "origin", "destination", "priority"):
            if getattr(self, field) is not None:
                q[field] = getattr(self, field)
        if self.created_from or self.created_to:
            q["created_at"] = {}
            if self.created_from:
                q["created_at"]["$gte"] = self.created_from
            if self.created_to:
                q["created_at"]["$lte"] = self.created_to
        if self.id_prefix:
            q["_id"] = {"$regex": "^" + re.escape(self.id_prefix)}
        return q


class MissionRepository(Protocol):
    async def init(self) -> None: ...
    async def save_many(self, missions: list[Mission]) -> None: ...
    async def get(self, mission_id: str) -> Mission | None: ...
    async def find(self, flt: MissionFilter | None = None, limit: int = 100, offset: int = 0) -> list[Mission]: ...
    async def count(self, flt: MissionFilter | None = None) -> int: ...
    async def save_robots(self, robots: list[Robot]) -> None: ...
    async def load_robots(self) -> dict[str, dict]: ...
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
        self._robots = self._client[db]["robots"]

    async def init(self) -> None:
        await self._col.create_index([("state", 1), ("created_at", -1)])
        await self._col.create_index([("robot_id", 1), ("created_at", -1)])
        await self._col.create_index([("created_at", -1)])

    async def save_many(self, missions: list[Mission]) -> None:
        if not missions:
            return
        ops = [ReplaceOne({"_id": m.id}, to_doc(m), upsert=True) for m in missions]
        await self._col.bulk_write(ops, ordered=False)

    async def get(self, mission_id: str) -> Mission | None:
        doc = await self._col.find_one({"_id": mission_id})
        return from_doc(doc) if doc else None

    async def find(self, flt: MissionFilter | None = None, limit: int = 100, offset: int = 0) -> list[Mission]:
        query = flt.to_mongo() if flt else {}
        cursor = self._col.find(query).sort("created_at", -1).skip(offset).limit(limit)
        return [from_doc(d) async for d in cursor]

    async def count(self, flt: MissionFilter | None = None) -> int:
        return await self._col.count_documents(flt.to_mongo() if flt else {})

    async def save_robots(self, robots: list[Robot]) -> None:
        if robots:
            ops = [ReplaceOne({"_id": r.id}, robot_doc(r), upsert=True) for r in robots]
            await self._robots.bulk_write(ops, ordered=False)

    async def load_robots(self) -> dict[str, dict]:
        return {d["_id"]: d async for d in self._robots.find({})}

    async def list_active(self) -> list[Mission]:
        query = {"state": {"$in": [s.value for s in ACTIVE_MISSION_STATES]}}
        return [from_doc(d) async for d in self._col.find(query)]

    async def close(self) -> None:
        await self._client.close()


class InMemoryMissionRepository:
    """Guarda copias, para simular que lo persistido no cambia por referencia."""

    def __init__(self, missions: list[Mission] | None = None):
        self._data: dict[str, Mission] = {m.id: replace(m) for m in missions or []}
        self.robots: dict[str, dict] = {}

    async def save_robots(self, robots: list[Robot]) -> None:
        for r in robots:
            self.robots[r.id] = robot_doc(r)

    async def load_robots(self) -> dict[str, dict]:
        return {k: dict(v) for k, v in self.robots.items()}

    async def init(self) -> None:
        pass

    async def save_many(self, missions: list[Mission]) -> None:
        for m in missions:
            self._data[m.id] = replace(m)

    async def get(self, mission_id: str) -> Mission | None:
        m = self._data.get(mission_id)
        return replace(m) if m else None

    async def find(self, flt: MissionFilter | None = None, limit: int = 100, offset: int = 0) -> list[Mission]:
        ms = [m for m in self._data.values() if flt is None or flt.matches(m)]
        ms.sort(key=lambda m: m.created_at, reverse=True)
        return [replace(m) for m in ms[offset:offset + limit]]

    async def count(self, flt: MissionFilter | None = None) -> int:
        return sum(1 for m in self._data.values() if flt is None or flt.matches(m))

    async def list_active(self) -> list[Mission]:
        return [replace(m) for m in self._data.values() if m.state in ACTIVE_MISSION_STATES]

    async def close(self) -> None:
        pass
