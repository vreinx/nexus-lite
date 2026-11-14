# NEXUS Lite

Mini gestor de flota AMR: un backend que simula 5 robots en un almacén de 20 × 12 celdas, asigna misiones de transporte y envía los cambios en tiempo real a un frontend.

> En construcción. Este README se completa al final con arquitectura, decisiones, contrato de la API y horas dedicadas.

## Arranque

```bash
docker compose up --build
```

- Backend: http://localhost:8000 (documentación OpenAPI en http://localhost:8000/docs)
- InfluxDB: http://localhost:8086 (admin / nexus-admin-pass)

## Tests

```bash
cd backend
pip install -r requirements.txt
pytest
```

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python 3.12 + FastAPI |
| Tiempo real | WebSocket |
| Misiones | MongoDB |
| Telemetría | InfluxDB 2 |
| Frontend | Svelte (pendiente) |

## Mapa

Definido en `backend/config/map.json` y validado al arrancar (si hay un error, el backend no arranca).

| Elemento | Posición |
|---|---|
| P1–P4 (recogida) | columna izquierda: (0,1), (0,4), (0,7), (0,10) |
| D1–D2 (entrega) | columna derecha: (19,3), (19,8) |
| C1 (carga, 2 plazas) | (10,0), cola de espera en (10,1) |
| R1–R5 | fila inferior: (8..12, 11) |
