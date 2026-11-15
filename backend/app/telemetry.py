"""B-05: telemetría de robots (posición, batería y estado) en InfluxDB.

En cada tick se escribe un punto por robot:
  measurement: robot_telemetry
  tag:         robot_id          (pocos valores -> baja cardinalidad)
  fields:      x, y, battery, state
El estado va como field y no como tag para no multiplicar las series
(una serie por robot, no una por robot y estado).
"""
from datetime import datetime
from typing import Protocol

from influxdb_client import Point
from influxdb_client.client.influxdb_client_async import InfluxDBClientAsync

from app.domain.models import Robot

MEASUREMENT = "robot_telemetry"


class TelemetryStore(Protocol):
    async def write(self, robots: list[Robot], ts: datetime) -> None: ...
    async def history(self, robot_id: str, minutes: int, every_s: int) -> list[dict]: ...
    async def close(self) -> None: ...


class InfluxTelemetryStore:
    def __init__(self, url: str, token: str, org: str, bucket: str):
        self._client = InfluxDBClientAsync(url=url, token=token, org=org)
        self._bucket = bucket
        self._write = self._client.write_api()
        self._query = self._client.query_api()

    async def write(self, robots: list[Robot], ts: datetime) -> None:
        points = [
            Point(MEASUREMENT)
            .tag("robot_id", r.id)
            .field("x", r.x)
            .field("y", r.y)
            .field("battery", float(r.battery))
            .field("state", r.state.value)
            .time(ts)
            for r in robots
        ]
        await self._write.write(bucket=self._bucket, record=points)

    async def history(self, robot_id: str, minutes: int, every_s: int) -> list[dict]:
        # robot_id ya viene validado contra los robots existentes (no hay inyección en Flux)
        flux = f'''
from(bucket: "{self._bucket}")
  |> range(start: -{int(minutes)}m)
  |> filter(fn: (r) => r._measurement == "{MEASUREMENT}" and r.robot_id == "{robot_id}")
  |> aggregateWindow(every: {int(every_s)}s, fn: last, createEmpty: false)
  |> pivot(rowKey: ["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> sort(columns: ["_time"])
'''
        tables = await self._query.query(flux)
        return [
            {
                "time": rec.get_time().isoformat(),
                "x": rec.values.get("x"),
                "y": rec.values.get("y"),
                "battery": rec.values.get("battery"),
                "state": rec.values.get("state"),
            }
            for table in tables
            for rec in table.records
        ]

    async def close(self) -> None:
        await self._client.close()


class InMemoryTelemetryStore:
    """Para tests: guarda los puntos en una lista."""

    def __init__(self) -> None:
        self.points: list[dict] = []

    async def write(self, robots: list[Robot], ts: datetime) -> None:
        self.points += [
            {"time": ts.isoformat(), "robot_id": r.id, "x": r.x, "y": r.y,
             "battery": r.battery, "state": r.state.value}
            for r in robots
        ]

    async def history(self, robot_id: str, minutes: int, every_s: int) -> list[dict]:
        return [{k: v for k, v in p.items() if k != "robot_id"}
                for p in self.points if p["robot_id"] == robot_id]

    async def close(self) -> None:
        pass
