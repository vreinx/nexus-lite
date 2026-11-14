"""Contrato de la API (entrada y salida). FastAPI genera el OpenAPI a partir de aquí."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models import PRIORITY_MAX, PRIORITY_MIN, Mission, MissionState, Robot, RobotState


class MissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", json_schema_extra={
        "examples": [{"origin": "P1", "destination": "D2", "priority": 1}]
    })

    origin: str = Field(min_length=1, max_length=10, description="Estación de recogida (P1..P4)")
    destination: str = Field(min_length=1, max_length=10, description="Estación de entrega (D1..D2)")
    priority: int = Field(ge=PRIORITY_MIN, le=PRIORITY_MAX, description="1 = máxima, 3 = mínima")


class MissionOut(BaseModel):
    id: str
    origin: str
    destination: str
    priority: int
    state: MissionState
    robot_id: str | None
    created_at: datetime
    updated_at: datetime | None
    reason: str | None

    @classmethod
    def of(cls, m: Mission) -> "MissionOut":
        return cls(id=m.id, origin=m.origin, destination=m.destination, priority=m.priority,
                   state=m.state, robot_id=m.robot_id, created_at=m.created_at,
                   updated_at=m.updated_at, reason=m.reason)


class RobotOut(BaseModel):
    id: str
    x: int
    y: int
    battery: float
    state: RobotState
    mission_id: str | None
    target: tuple[int, int] | None

    @classmethod
    def of(cls, r: Robot) -> "RobotOut":
        return cls(id=r.id, x=r.x, y=r.y, battery=round(r.battery, 1), state=r.state,
                   mission_id=r.mission_id, target=r.target)


class ErrorOut(BaseModel):
    detail: str
