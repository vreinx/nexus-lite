"""Carga y validación del fichero de configuración del mapa (config/map.json).

Si el fichero tiene un error (estación fuera de la cuadrícula, id repetido,
faltan P/D/C...) el backend no arranca: mejor fallar al inicio que simular
un almacén incoherente.
"""
import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, model_validator


class StationType(str, Enum):
    PICKUP = "PICKUP"
    DROP = "DROP"
    CHARGER = "CHARGER"
    PARKING = "PARKING"


# Tipos obligatorios en cualquier mapa (los parkings son opcionales).
REQUIRED_STATION_TYPES = (StationType.PICKUP, StationType.DROP, StationType.CHARGER)


class Cell(BaseModel):
    x: int = Field(ge=0)
    y: int = Field(ge=0)


class Grid(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)


class Station(Cell):
    id: str
    type: StationType
    capacity: int = Field(default=1, ge=1)  # solo relevante en CHARGER
    queue: Cell | None = None               # celda de espera del cargador
    # Plazas del cargador: una celda por plaza (dos robots nunca comparten celda).
    # Si no se indican, se usan celdas contiguas a la derecha de (x, y).
    bays: list[Cell] | None = None

    @property
    def cells(self) -> list[tuple[int, int]]:
        """Celdas que ocupa la estación (más de una si es un cargador con varias plazas)."""
        if self.bays:
            return [(b.x, b.y) for b in self.bays]
        return [(self.x, self.y)]


class RobotInit(Cell):
    id: str
    battery: float = Field(default=100, ge=0, le=100)


class SimulationParams(BaseModel):
    tick_seconds: float = Field(default=1.0, gt=0)
    battery_per_cell: float = Field(default=0.5, ge=0)
    charge_per_second: float = Field(default=2.0, ge=0)
    load_seconds: int = Field(default=3, ge=0)
    unload_seconds: int = Field(default=3, ge=0)
    min_battery_to_assign: float = Field(default=30, ge=0, le=100)
    low_battery_threshold: float = Field(default=20, ge=0, le=100)
    charge_target: float = Field(default=100, gt=0, le=100)  # sale de C1 al llegar a este %


class MapConfig(BaseModel):
    grid: Grid
    stations: list[Station]
    robots: list[RobotInit]
    simulation: SimulationParams = SimulationParams()

    @model_validator(mode="after")
    def _check(self) -> "MapConfig":
        for s in self.stations:
            if s.type == StationType.CHARGER:
                if s.bays is None:
                    s.bays = [Cell(x=s.x + i, y=s.y) for i in range(s.capacity)]
                if len(s.bays) != s.capacity:
                    raise ValueError(f"{s.id}: el número de plazas debe coincidir con la capacidad")

        def inside(c: Cell, what: str) -> None:
            if c.x >= self.grid.width or c.y >= self.grid.height:
                raise ValueError(f"{what} ({c.x},{c.y}) fuera de la cuadrícula")

        ids = [s.id for s in self.stations] + [r.id for r in self.robots]
        dup = {i for i in ids if ids.count(i) > 1}
        if dup:
            raise ValueError(f"ids repetidos: {sorted(dup)}")

        cells = [c for s in self.stations for c in s.cells]
        cells += [(s.queue.x, s.queue.y) for s in self.stations if s.queue]
        dup_cells = {c for c in cells if cells.count(c) > 1}
        if dup_cells:
            raise ValueError(f"varias estaciones en la misma celda: {sorted(dup_cells)}")

        robot_cells = [(r.x, r.y) for r in self.robots]
        dup_robots = {c for c in robot_cells if robot_cells.count(c) > 1}
        if dup_robots:
            raise ValueError(f"varios robots empiezan en la misma celda: {sorted(dup_robots)}")

        for s in self.stations:
            inside(s, s.id)
            for b in s.bays or []:
                inside(b, f"plaza de {s.id}")
            if s.queue:
                inside(s.queue, f"cola de {s.id}")
        for r in self.robots:
            inside(r, r.id)

        for t in REQUIRED_STATION_TYPES:
            if not any(s.type == t for s in self.stations):
                raise ValueError(f"falta al menos una estación {t.value}")
        if len(self.stations_of(StationType.CHARGER)) != 1:
            raise ValueError("debe haber exactamente un CHARGER")
        return self

    # Accesos de conveniencia
    def station(self, station_id: str) -> Station | None:
        return next((s for s in self.stations if s.id == station_id), None)

    def stations_of(self, t: StationType) -> list[Station]:
        return [s for s in self.stations if s.type == t]

    @property
    def charger(self) -> Station:
        return self.stations_of(StationType.CHARGER)[0]


def load_map(path: str | Path) -> MapConfig:
    with open(path, encoding="utf-8") as f:
        return MapConfig.model_validate(json.load(f))
