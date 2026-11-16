"""Configuración por variables de entorno (las define docker-compose.yml)."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    map_file: str = "config/map.json"

    mongo_url: str = "mongodb://localhost:27017"
    mongo_db: str = "nexus_lite"

    influx_url: str = "http://localhost:8086"
    influx_token: str = "nexus-dev-token"
    influx_org: str = "andyor"
    influx_bucket: str = "telemetry"

    # Autenticación (extra). Valores de desarrollo: cambiarlos fuera del ejercicio.
    auth_secret: str = "nexus-lite-dev-secret-cambiar-en-produccion"
    token_hours: int = 8
    operator_password: str = "operador"
    viewer_password: str = "consulta"


settings = Settings()
