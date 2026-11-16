"""A* en la cuadrícula (4 vecinos, coste 1 por celda, heurística Manhattan).

Se usa para rodear obstáculos fijos: robots que no se van a mover pronto
(ERROR, cargando batería, cargando/descargando mercancía) y casillas de entrega
con un palet recién entregado. Los robots en movimiento NO son obstáculos aquí:
esos cruces se resuelven tick a tick con las reglas de prioridad del simulador.

A igualdad de coste se prefiere moverse primero en X y luego en Y, para que las
rutas se parezcan a la "L" del enunciado cuando no hay nada en medio.
"""
import heapq
from itertools import count

Pos = tuple[int, int]


def manhattan(a: Pos, b: Pos) -> int:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def astar(start: Pos, goal: Pos, width: int, height: int, blocked: set[Pos]) -> list[Pos] | None:
    """Camino más corto de start a goal (sin incluir start, incluyendo goal).

    Devuelve [] si ya está en el destino y None si no hay camino.
    El destino se considera transitable aunque esté en `blocked`.
    """
    if start == goal:
        return []
    tie = count()
    # (f, h, orden de inserción, celda): a igual f, el más cercano al destino;
    # a igual h, el que se generó antes (X antes que Y).
    open_heap = [(manhattan(start, goal), manhattan(start, goal), next(tie), start)]
    came_from: dict[Pos, Pos] = {}
    g = {start: 0}
    closed: set[Pos] = set()

    while open_heap:
        _, _, _, cur = heapq.heappop(open_heap)
        if cur == goal:
            path = [cur]
            while path[-1] in came_from and came_from[path[-1]] != start:
                path.append(came_from[path[-1]])
            return path[::-1]
        if cur in closed:
            continue
        closed.add(cur)

        x, y = cur
        dx = 1 if goal[0] > x else -1
        dy = 1 if goal[1] > y else -1
        # Primero los vecinos que acercan (X y luego Y), después el resto
        for nxt in ((x + dx, y), (x, y + dy), (x - dx, y), (x, y - dy)):
            nx, ny = nxt
            if not (0 <= nx < width and 0 <= ny < height):
                continue
            if nxt in blocked and nxt != goal:
                continue
            ng = g[cur] + 1
            if ng < g.get(nxt, 1 << 30):
                g[nxt] = ng
                came_from[nxt] = cur
                h = manhattan(nxt, goal)
                heapq.heappush(open_heap, (ng + h, h, next(tie), nxt))
    return None
