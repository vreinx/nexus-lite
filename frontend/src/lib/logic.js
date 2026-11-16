// Lógica pura del frontend (sin Svelte ni DOM), para poder testearla aislada.

export const batteryColor = (b) => (b < 20 ? '#d1495b' : b < 30 ? '#e0a458' : '#6ca087');

/**
 * Orientación (grados) de un robot: hacia su siguiente celda. 0 = derecha,
 * 90 = abajo (el eje Y del SVG crece hacia abajo). Si está parado conserva la
 * anterior. Acumula el giro por el camino más corto (de 350° a 10° gira +20°,
 * no -340°), para que la animación no dé la vuelta entera.
 */
export function nextHeading(prev, robot) {
  const next = robot.path?.[0] ?? null;
  let target = null;
  if (next) {
    const [nx, ny] = next;
    if (nx !== robot.x) target = nx > robot.x ? 0 : 180;
    else if (ny !== robot.y) target = ny > robot.y ? 90 : -90;
  } else if (robot.target) {
    const [tx, ty] = robot.target;
    if (robot.x !== tx) target = tx > robot.x ? 0 : 180;
    else if (robot.y !== ty) target = ty > robot.y ? 90 : -90;
  }
  if (target === null) return prev;
  const delta = ((((target - prev) % 360) + 540) % 360) - 180;
  return prev + delta;
}

/** Puntos de la polilínea de la ruta (ruta A* del backend, o la "L" si no hay). */
export function routeCells(robot) {
  if (!robot.target) return [];
  if (robot.path?.length) return [[robot.x, robot.y], ...robot.path];
  const [tx, ty] = robot.target;
  return [[robot.x, robot.y], [tx, robot.y], [tx, ty]];
}

/** Parámetros de consulta del historial a partir de los filtros de la vista. */
export function missionQuery(filters, limit, offset) {
  const q = new URLSearchParams();
  for (const st of filters.states ?? []) q.append('state', st);
  for (const k of ['robot_id', 'origin', 'destination', 'priority', 'id_prefix']) {
    if (filters[k]) q.set(k, filters[k]);
  }
  // Los <input type="datetime-local"> dan hora local sin zona: se pasan a ISO UTC
  for (const k of ['created_from', 'created_to']) {
    if (filters[k]) q.set(k, new Date(filters[k]).toISOString());
  }
  q.set('limit', limit);
  q.set('offset', offset);
  return q;
}

/** Duración de una orden terminada ("42 s", "1 min 12 s") o "—". */
export function formatDuration(m) {
  if (!['DONE', 'FAILED', 'CANCELLED'].includes(m.state) || !m.updated_at) return '—';
  const s = Math.round((new Date(m.updated_at) - new Date(m.created_at)) / 1000);
  return s < 60 ? `${s} s` : `${Math.floor(s / 60)} min ${s % 60} s`;
}

/**
 * Trazado SVG de la batería en el tiempo. points: [{time, battery}], ordenados.
 * Devuelve { line, area } (atributo "d") dentro de un rectángulo w x h, con el
 * eje Y fijo de 0 a 100 % para que los gráficos de distintos robots se comparen.
 */
export function batteryPath(points, w, h) {
  if (!points.length) return { line: '', area: '' };
  const t0 = new Date(points[0].time).getTime();
  const t1 = new Date(points[points.length - 1].time).getTime();
  const span = Math.max(1, t1 - t0);
  const xy = points.map((p) => [
    ((new Date(p.time).getTime() - t0) / span) * w,
    h - (Math.max(0, Math.min(100, p.battery)) / 100) * h,
  ]);
  const line = xy.map(([x, y], i) => `${i ? 'L' : 'M'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${xy[xy.length - 1][0].toFixed(1)},${h} L${xy[0][0].toFixed(1)},${h} Z`;
  return { line, area };
}
