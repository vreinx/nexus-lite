"""Autenticación con dos roles (extra opcional del enunciado).

  - OPERATOR ("operador"): ve todo y puede actuar (crear y cancelar órdenes,
    reenviar, declarar/retirar palets, forzar ERROR y rearmar robots).
  - VIEWER ("consulta"): solo puede consultar.

Login con usuario y contraseña -> token JWT firmado (HS256) con el usuario, el
rol y la caducidad. Es sin estado: un reinicio del backend no cierra sesiones.
El token se envía en la cabecera "Authorization: Bearer <token>" y, en el
WebSocket (el navegador no permite cabeceras ahí), como ?token=<token>.

Para el ejercicio, los dos usuarios y sus contraseñas vienen de la
configuración (variables de entorno). En producción irían en base de datos con
contraseñas con hash (bcrypt/argon2) o en el proveedor de identidad de la planta.
"""
import hmac
from datetime import datetime, timedelta, timezone
from enum import Enum

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from app.settings import settings

ALGORITHM = "HS256"


class Role(str, Enum):
    OPERATOR = "OPERATOR"
    VIEWER = "VIEWER"


class User(BaseModel):
    username: str
    role: Role
    display_name: str


def _users() -> dict[str, tuple[str, User]]:
    return {
        "operador": (settings.operator_password,
                     User(username="operador", role=Role.OPERATOR, display_name="Operador")),
        "consulta": (settings.viewer_password,
                     User(username="consulta", role=Role.VIEWER, display_name="Consulta")),
    }


def authenticate(username: str, password: str) -> User | None:
    entry = _users().get(username)
    # compare_digest: tiempo constante, no da pistas sobre la contraseña
    if entry is None or not hmac.compare_digest(entry[0].encode(), password.encode()):
        return None
    return entry[1]


def create_token(user: User, now: datetime | None = None) -> str:
    now = now or datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role.value,
        "name": user.display_name,
        "iat": now,
        "exp": now + timedelta(hours=settings.token_hours),
    }
    return jwt.encode(payload, settings.auth_secret, algorithm=ALGORITHM)


def decode_token(token: str) -> User | None:
    try:
        p = jwt.decode(token, settings.auth_secret, algorithms=[ALGORITHM])
        return User(username=p["sub"], role=Role(p["role"]), display_name=p["name"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None


_bearer = HTTPBearer(auto_error=False, description="Token de POST /api/v1/auth/login")


def require_user(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> User:
    """Cualquier usuario con sesión válida (operador o consulta). Si no: 401."""
    user = decode_token(creds.credentials) if creds else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sesión no válida o caducada",
                            headers={"WWW-Authenticate": "Bearer"})
    return user


def require_operator(user: User = Depends(require_user)) -> User:
    """Solo el rol operador. Con el rol de consulta: 403."""
    if user.role != Role.OPERATOR:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "tu rol (consulta) solo permite ver")
    return user
