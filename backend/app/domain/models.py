"""Entidades del dominio: robots y misiones.

Son dataclasses sin dependencias de base de datos ni de FastAPI, para poder
testear la lógica de forma aislada.
"""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class RobotState(str, Enum):
    IDLE = "IDLE"
    TO_PICKUP = "TO_PICKUP"
    LOADING = "LOADING"
    TO_DROP = "TO_DROP"
    UNLOADING = "UNLOADING"
    TO_CHARGER = "TO_CHARGER"
    CHARGING = "CHARGING"
    ERROR = "ERROR"


class MissionState(str, Enum):
    PENDING = "PENDING"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    CANCELLED = "CANCELLED"
    FAILED = "FAILED"


ACTIVE_MISSION_STATES = {MissionState.PENDING, MissionState.ASSIGNED, MissionState.IN_PROGRESS}

# Prioridad: 1 = máxima, 3 = mínima (como una P1 de incidencias).
PRIORITY_MIN, PRIORITY_MAX = 1, 3


@dataclass
class Robot:
    id: str
    x: int
    y: int
    battery: float = 100.0
    state: RobotState = RobotState.IDLE
    mission_id: str | None = None
    target: tuple[int, int] | None = None   # celda a la que se dirige
    timer: int = 0                          # segundos restantes de LOADING / UNLOADING

    @property
    def pos(self) -> tuple[int, int]:
        return (self.x, self.y)


@dataclass
class Mission:
    id: str
    origin: str          # id de estación de recogida (P1..P4)
    destination: str     # id de estación de entrega (D1..D2)
    priority: int        # 1 (máxima) .. 3 (mínima)
    created_at: datetime
    state: MissionState = MissionState.PENDING
    robot_id: str | None = None
    updated_at: datetime | None = None
    reason: str | None = None   # motivo si termina en FAILED / CANCELLED
