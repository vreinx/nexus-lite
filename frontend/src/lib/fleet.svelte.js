// Estado compartido de la aplicación + conexión WebSocket (B-04 / F-04).
//
// El backend manda un "snapshot" al conectar y después "update" solo con lo
// que cambia. Si se cae la conexión, se reintenta con espera creciente
// (1 s, 2 s, 4 s... hasta 10 s) y al reconectar llega otro snapshot que
// resincroniza lo que se perdiera.

const MAX_MISSIONS = 200;

export const fleet = $state({
  map: null,
  robots: {},          // id -> robot
  missions: {},        // id -> misión
  stations: {},        // id -> { pallet, clears_in, reserved_by, since }
  connection: 'connecting', // 'connecting' | 'online' | 'offline'
  retryIn: 0,          // segundos hasta el próximo intento
  selectedRobot: null,
  lastUpdate: null,
  missionsVersion: 0,  // se incrementa cuando llegan cambios de misiones (el historial se refresca)
  user: null,          // { username, role, display_name } con sesión iniciada
  authMessage: '',     // p. ej. "Sesión caducada" al volver a la pantalla de login
});

// --------------------------------------------------------------- sesión
// El token se guarda en sessionStorage: sobrevive a recargar la página pero no
// a cerrar la pestaña. Las acciones las protege el backend (401 / 403); el
// frontend solo oculta lo que el rol no puede hacer.
const TOKEN_KEY = 'nexus-lite-token';
let token = null;
try {
  token = sessionStorage.getItem(TOKEN_KEY);
} catch {
  token = null;
}

export const isOperator = () => fleet.user?.role === 'OPERATOR';

// Colores de estado armonizados con el verde corporativo (CHARGING = verde marca).
export const ROBOT_COLORS = {
  IDLE: '#9aa8a1',
  TO_PICKUP: '#4a90a4',
  LOADING: '#6f7fc0',
  TO_DROP: '#e0a458',
  UNLOADING: '#d9824f',
  TO_CHARGER: '#5fb3a1',
  CHARGING: '#6ca087',
  ERROR: '#d1495b',
};

import { missionQuery } from './logic.js';
export { batteryColor } from './logic.js';

let ws = null;
let backoff = 1000;
let retryTimer = null;
let countdownTimer = null;

function applyRobots(list) {
  for (const r of list) fleet.robots[r.id] = r;
}

function applyMissions(list) {
  for (const m of list) fleet.missions[m.id] = m;
  const ids = Object.keys(fleet.missions);
  if (ids.length > MAX_MISSIONS) {
    // Se descartan las terminadas más antiguas para no crecer sin límite.
    const done = Object.values(fleet.missions)
      .filter((m) => !['PENDING', 'ASSIGNED', 'IN_PROGRESS'].includes(m.state))
      .sort((a, b) => a.created_at.localeCompare(b.created_at));
    for (const m of done.slice(0, ids.length - MAX_MISSIONS)) delete fleet.missions[m.id];
  }
}

function applyStations(list) {
  for (const s of list) {
    const prev = fleet.stations[s.id];
    // Marca de cuándo aparece un palet entregado (para reiniciar el temporizador)
    const since = s.clears_in != null && !(prev?.pallet) ? Date.now() : prev?.since;
    fleet.stations[s.id] = { ...s, since };
  }
}

function onMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === 'snapshot') {
    fleet.robots = {};
    fleet.missions = {};
    fleet.stations = {};
  }
  applyRobots(msg.robots);
  applyMissions(msg.missions);
  applyStations(msg.stations ?? []);
  if (msg.missions.length) fleet.missionsVersion++;
  fleet.lastUpdate = new Date();
}

function scheduleReconnect() {
  clearTimeout(retryTimer);
  clearInterval(countdownTimer);
  fleet.retryIn = Math.round(backoff / 1000);
  countdownTimer = setInterval(() => {
    fleet.retryIn = Math.max(0, fleet.retryIn - 1);
  }, 1000);
  retryTimer = setTimeout(connect, backoff);
  backoff = Math.min(backoff * 2, 10000);
}

export function connect() {
  clearInterval(countdownTimer);
  if (!token) return;                 // sin sesión no hay tiempo real
  fleet.connection = 'connecting';
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);

  ws.onopen = () => {
    fleet.connection = 'online';
    backoff = 1000;
  };
  ws.onmessage = onMessage;
  ws.onclose = () => {
    fleet.connection = 'offline';
    if (token) scheduleReconnect();   // tras cerrar sesión no se reintenta
  };
  // onerror siempre va seguido de onclose: la reconexión se gestiona allí.
  ws.onerror = () => {};
}

export function reconnectNow() {
  backoff = 1000;
  clearTimeout(retryTimer);
  connect();
}

// ---------------------------------------------------------------- API REST
async function request(method, url, body, withResponse = false) {
  let res;
  try {
    const headers = body ? { 'Content-Type': 'application/json' } : {};
    if (token) headers.Authorization = `Bearer ${token}`;
    res = await fetch(url, { method, headers, body: body ? JSON.stringify(body) : undefined });
  } catch {
    throw new Error('No se puede contactar con el backend');
  }
  const data = await res.json().catch(() => null);
  if (res.status === 401 && token) {
    logout('Tu sesión ha caducado. Vuelve a iniciar sesión.');
  }
  if (!res.ok) {
    // FastAPI devuelve {detail: "..."} o {detail: [{msg: ...}]} en los 422
    const d = data?.detail;
    const text = Array.isArray(d) ? d.map((e) => e.msg).join('; ') : d;
    throw new Error(text || `Error ${res.status}`);
  }
  return withResponse ? { data, res } : data;
}

export async function loadMap() {
  fleet.map = await request('GET', '/api/v1/map');
}

export async function createMission(origin, destination, priority) {
  const m = await request('POST', '/api/v1/missions', { origin, destination, priority });
  applyMissions([m]);
  return m;
}

export async function cancelMission(id) {
  const m = await request('POST', `/api/v1/missions/${id}/cancel`);
  applyMissions([m]);
  return m;
}

// ------------------------------------------------------------ historial
// filters: { states: [], robot_id, origin, destination, priority, created_from, created_to, id_prefix }
export async function fetchMissions(filters, limit, offset) {
  const q = missionQuery(filters, limit, offset);
  const { data, res } = await request('GET', `/api/v1/missions?${q}`, undefined, true);
  return { items: data, total: Number(res.headers.get('X-Total-Count') ?? data.length) };
}

export async function retryMission(id, robotId) {
  const m = await request('POST', `/api/v1/missions/${id}/retry`, { robot_id: robotId || null });
  applyMissions([m]);
  fleet.missionsVersion++;
  return m;
}

// ---------------------------------------------------------------- palets
export async function declarePallet(stationId) {
  const s = await request('POST', `/api/v1/stations/${stationId}/pallet`);
  applyStations([s]);
  return s;
}

export async function removePallet(stationId) {
  const s = await request('DELETE', `/api/v1/stations/${stationId}/pallet`);
  applyStations([s]);
  return s;
}

// ---------------------------------------------------------------- operador
export async function forceError(robotId) {
  const r = await request('POST', `/api/v1/robots/${robotId}/error`);
  applyRobots([r]);
  return r;
}

export async function resetRobot(robotId) {
  const r = await request('POST', `/api/v1/robots/${robotId}/reset`);
  applyRobots([r]);
  return r;
}

export async function fetchTelemetry(robotId, minutes = 10, every = 5) {
  return request('GET', `/api/v1/robots/${robotId}/telemetry?minutes=${minutes}&every=${every}`);
}

// --------------------------------------------------------------- sesión
export async function login(username, password) {
  const r = await request('POST', '/api/v1/auth/login', { username, password });
  token = r.token;
  try {
    sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* sin almacenamiento: la sesión dura lo que la pestaña abierta */
  }
  fleet.user = { username: r.username, role: r.role, display_name: r.display_name };
  fleet.authMessage = '';
  return fleet.user;
}

/** Recupera la sesión guardada (al recargar la página). */
export async function restoreSession() {
  if (!token) return null;
  try {
    fleet.user = await request('GET', '/api/v1/auth/me');
  } catch {
    fleet.user = null;
  }
  return fleet.user;
}

export function logout(message = '') {
  token = null;
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nada */
  }
  clearTimeout(retryTimer);
  clearInterval(countdownTimer);
  if (ws) {
    ws.onclose = null;
    ws.close();
    ws = null;
  }
  fleet.user = null;
  fleet.authMessage = message;
  fleet.connection = 'connecting';
  fleet.robots = {};
  fleet.missions = {};
  fleet.stations = {};
  fleet.selectedRobot = null;
}
