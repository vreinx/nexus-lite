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
  connection: 'connecting', // 'connecting' | 'online' | 'offline'
  retryIn: 0,          // segundos hasta el próximo intento
  selectedRobot: null,
  lastUpdate: null,
});

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

export const batteryColor = (b) => (b < 20 ? '#d1495b' : b < 30 ? '#e0a458' : '#6ca087');

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

function onMessage(event) {
  const msg = JSON.parse(event.data);
  if (msg.type === 'snapshot') {
    fleet.robots = {};
    fleet.missions = {};
  }
  applyRobots(msg.robots);
  applyMissions(msg.missions);
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
  fleet.connection = 'connecting';
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  ws = new WebSocket(`${proto}://${location.host}/ws`);

  ws.onopen = () => {
    fleet.connection = 'online';
    backoff = 1000;
  };
  ws.onmessage = onMessage;
  ws.onclose = () => {
    fleet.connection = 'offline';
    scheduleReconnect();
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
async function request(method, url, body) {
  let res;
  try {
    res = await fetch(url, {
      method,
      headers: body ? { 'Content-Type': 'application/json' } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new Error('No se puede contactar con el backend');
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) {
    // FastAPI devuelve {detail: "..."} o {detail: [{msg: ...}]} en los 422
    const d = data?.detail;
    const text = Array.isArray(d) ? d.map((e) => e.msg).join('; ') : d;
    throw new Error(text || `Error ${res.status}`);
  }
  return data;
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
