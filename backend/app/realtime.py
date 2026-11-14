"""B-04: difusión en tiempo real por WebSocket.

Protocolo (servidor -> navegador, JSON):
  {"type": "snapshot", "robots": [...], "missions": [...]}   al conectar
  {"type": "update",   "robots": [...], "missions": [...]}   solo lo que ha cambiado

Al reconectar, el cliente recibe otro snapshot: así recupera lo que se
perdió mientras estuvo desconectado sin necesidad de numerar mensajes.
"""
import asyncio
import json
import logging

from fastapi import WebSocket

from app.domain.models import Mission, Robot
from app.schemas import MissionOut, RobotOut

log = logging.getLogger("nexus.realtime")

SEND_TIMEOUT_S = 1.0   # un cliente lento no puede frenar el simulador


def encode(kind: str, robots: list[Robot], missions: list[Mission]) -> str:
    return json.dumps({
        "type": kind,
        "robots": [RobotOut.of(r).model_dump(mode="json") for r in robots],
        "missions": [MissionOut.of(m).model_dump(mode="json") for m in missions],
    })


class ConnectionManager:
    def __init__(self) -> None:
        self._clients: set[WebSocket] = set()

    @property
    def count(self) -> int:
        return len(self._clients)

    def add(self, ws: WebSocket) -> None:
        self._clients.add(ws)

    def remove(self, ws: WebSocket) -> None:
        self._clients.discard(ws)

    async def broadcast(self, robots: list[Robot], missions: list[Mission]) -> None:
        if not self._clients or (not robots and not missions):
            return
        message = encode("update", robots, missions)
        clients = list(self._clients)
        results = await asyncio.gather(
            *(asyncio.wait_for(ws.send_text(message), SEND_TIMEOUT_S) for ws in clients),
            return_exceptions=True,
        )
        for ws, result in zip(clients, results):
            if isinstance(result, Exception):
                log.info("Cliente WebSocket descartado: %r", result)
                self.remove(ws)
