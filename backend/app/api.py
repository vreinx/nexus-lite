"""B-01 / B-07: endpoints REST.

Códigos de error:
  404 recurso no existe · 409 transición no permitida (cancelar algo en curso
  o terminado) · 422 entrada no válida · 503 base de datos no disponible.
"""
from fastapi import APIRouter, HTTPException, Query, Request, status

from app.domain.models import MissionState
from app.domain.simulator import MissionError
from app.schemas import ErrorOut, MissionCreate, MissionOut, RobotOut
from app.service import FleetService, RepositoryUnavailable

router = APIRouter(prefix="/api/v1")


def _service(request: Request) -> FleetService:
    return request.app.state.service


# ------------------------------------------------------------------ misiones
@router.post(
    "/missions",
    status_code=status.HTTP_201_CREATED,
    response_model=MissionOut,
    tags=["misiones"],
    responses={422: {"model": ErrorOut}, 503: {"model": ErrorOut}},
)
async def create_mission(body: MissionCreate, request: Request):
    try:
        m = await _service(request).create_mission(body.origin, body.destination, body.priority)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except RepositoryUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    return MissionOut.of(m)


@router.get("/missions", response_model=list[MissionOut], tags=["misiones"])
async def list_missions(
    request: Request,
    state: MissionState | None = Query(default=None, description="Filtrar por estado"),
    limit: int = Query(default=100, ge=1, le=500),
):
    """Misiones ordenadas de más reciente a más antigua."""
    return [MissionOut.of(m) for m in await _service(request).list_missions(state, limit)]


@router.get("/missions/{mission_id}", response_model=MissionOut, tags=["misiones"],
            responses={404: {"model": ErrorOut}})
async def get_mission(mission_id: str, request: Request):
    m = await _service(request).get_mission(mission_id)
    if m is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "misión no encontrada")
    return MissionOut.of(m)


@router.post(
    "/missions/{mission_id}/cancel",
    response_model=MissionOut,
    tags=["misiones"],
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}},
)
async def cancel_mission(mission_id: str, request: Request):
    """Cancela una misión PENDING o ASSIGNED. Es un cambio de estado, no un
    borrado: la misión se conserva en el histórico como CANCELLED."""
    try:
        m = await _service(request).cancel_mission(mission_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "misión no encontrada")
    except MissionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    return MissionOut.of(m)


# -------------------------------------------------------------------- robots
@router.get("/robots", response_model=list[RobotOut], tags=["robots"])
async def list_robots(request: Request):
    return [RobotOut.of(r) for r in _service(request).list_robots()]


@router.get("/robots/{robot_id}/telemetry", tags=["robots"],
            responses={404: {"model": ErrorOut}, 503: {"model": ErrorOut}})
async def robot_telemetry(
    robot_id: str,
    request: Request,
    minutes: int = Query(default=10, ge=1, le=1440, description="Ventana hacia atrás"),
    every: int = Query(default=5, ge=1, le=3600, description="Agregación en segundos"),
):
    """Histórico de posición, batería y estado del robot (InfluxDB)."""
    service = _service(request)
    if service.get_robot(robot_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "robot no encontrado")
    if service.telemetry is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "telemetría no configurada")
    try:
        return await service.telemetry.history(robot_id, minutes, every)
    except Exception:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "InfluxDB no disponible")


@router.get("/robots/{robot_id}", response_model=RobotOut, tags=["robots"],
            responses={404: {"model": ErrorOut}})
async def get_robot(robot_id: str, request: Request):
    r = _service(request).get_robot(robot_id)
    if r is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "robot no encontrado")
    return RobotOut.of(r)
