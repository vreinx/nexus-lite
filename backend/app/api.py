"""B-01 / B-07: endpoints REST.

Códigos de error:
  404 recurso no existe · 409 conflicto con el estado actual (cancelar algo en
  curso o terminado, origen sin palet, palet ya asignado, destino ocupado,
  palet ya declarado) · 422 entrada no válida · 503 base de datos no disponible.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query, Request, Response, status

from app.domain.models import PRIORITY_MAX, PRIORITY_MIN, MissionState
from app.domain.simulator import MissionError
from app.repository import MissionFilter
from app.schemas import ErrorOut, MissionCreate, MissionOut, MissionRetry, RobotOut
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
    responses={409: {"model": ErrorOut}, 422: {"model": ErrorOut}, 503: {"model": ErrorOut}},
)
async def create_mission(body: MissionCreate, request: Request):
    """Crea una orden. Requiere palet en el origen sin otra orden asignada y
    destino libre (409 si no)."""
    try:
        m = await _service(request).create_mission(body.origin, body.destination, body.priority)
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except MissionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except RepositoryUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    return MissionOut.of(m)


@router.get("/missions", response_model=list[MissionOut], tags=["misiones"])
async def list_missions(
    request: Request,
    response: Response,
    state: list[MissionState] | None = Query(default=None, description="Uno o varios estados"),
    robot_id: str | None = Query(default=None),
    origin: str | None = Query(default=None),
    destination: str | None = Query(default=None),
    priority: int | None = Query(default=None, ge=PRIORITY_MIN, le=PRIORITY_MAX),
    created_from: datetime | None = Query(default=None, description="ISO 8601"),
    created_to: datetime | None = Query(default=None, description="ISO 8601"),
    id_prefix: str | None = Query(default=None, min_length=1, max_length=36),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """Historial de misiones, de más reciente a más antigua, con filtros y
    paginación. El total (para paginar) va en la cabecera X-Total-Count."""
    if created_from and created_to and created_from > created_to:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "created_from es posterior a created_to")
    flt = MissionFilter(states=state, robot_id=robot_id, origin=origin, destination=destination,
                        priority=priority, created_from=created_from, created_to=created_to,
                        id_prefix=id_prefix)
    items, total = await _service(request).list_missions(flt, limit, offset)
    response.headers["X-Total-Count"] = str(total)
    return [MissionOut.of(m) for m in items]


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


@router.post(
    "/missions/{mission_id}/retry",
    status_code=status.HTTP_201_CREATED,
    response_model=MissionOut,
    tags=["misiones"],
    responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}},
)
async def retry_mission(mission_id: str, request: Request, body: MissionRetry | None = None):
    """Reenvía una misión FAILED o CANCELLED como misión nueva (retry_of apunta
    a la original). Con robot_id, solo ese robot puede ejecutarla."""
    try:
        m = await _service(request).retry_mission(mission_id, body.robot_id if body else None)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "misión no encontrada")
    except MissionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except RepositoryUnavailable as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(e))
    return MissionOut.of(m)


# ------------------------------------------------------------------- palets
@router.get("/stations", tags=["palets"])
async def list_stations(request: Request):
    """Palets en estaciones de recogida y entrega. clears_in: segundos hasta que
    se retira el palet entregado; reserved_by: orden que tiene asignado el palet."""
    return _service(request).stations()


@router.post("/stations/{station_id}/pallet", status_code=status.HTTP_201_CREATED, tags=["palets"],
             responses={404: {"model": ErrorOut}, 409: {"model": ErrorOut}, 422: {"model": ErrorOut}})
async def declare_pallet(station_id: str, request: Request):
    """Declarar palet: el operador indica que ha dejado un palet en un origen."""
    try:
        return await _service(request).declare_pallet(station_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "estación no encontrada")
    except ValueError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))
    except MissionError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e))


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
