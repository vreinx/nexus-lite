<script>
  // Historial de órdenes: filtros, paginación, exportar a CSV y reenviar las
  // FAILED / CANCELLED (como misión nueva, opcionalmente a un robot concreto).
  import { fleet, fetchMissions, retryMission, isOperator } from '../lib/fleet.svelte.js';
  import { formatDuration as duration } from '../lib/logic.js';

  const STATES = ['PENDING', 'ASSIGNED', 'IN_PROGRESS', 'DONE', 'CANCELLED', 'FAILED'];
  const STATE_COLORS = {
    PENDING: '#8a9a93', ASSIGNED: '#4a90a4', IN_PROGRESS: '#d4903f',
    DONE: '#4f9a77', CANCELLED: '#b3bdb8', FAILED: '#c2414f',
  };
  const PAGE = 25;
  const EMPTY = { states: [], robot_id: '', origin: '', destination: '', priority: '',
                  created_from: '', created_to: '', id_prefix: '' };

  // Filtros iniciales desde el enlace, p. ej. #/historial?robot_id=R1&state=DONE
  function filtersFromHash() {
    const q = new URLSearchParams(location.hash.split('?')[1] ?? '');
    const f = { ...EMPTY, states: q.getAll('state').filter((s) => STATES.includes(s)) };
    for (const k of ['robot_id', 'origin', 'destination', 'priority', 'id_prefix']) {
      if (q.get(k)) f[k] = q.get(k);
    }
    return f;
  }

  let filters = $state(filtersFromHash());
  let page = $state(0);
  let items = $state([]);
  let total = $state(0);
  let loading = $state(false);
  let error = $state('');
  let notice = $state('');
  let retrying = $state(null);   // misión que se está reenviando
  let retryRobot = $state('');

  let pickups = $derived(fleet.map?.stations.filter((s) => s.type === 'PICKUP') ?? []);
  let drops = $derived(fleet.map?.stations.filter((s) => s.type === 'DROP') ?? []);
  let robots = $derived(Object.keys(fleet.robots).sort());
  let pages = $derived(Math.max(1, Math.ceil(total / PAGE)));
  let activeFilters = $derived(
    Object.entries(filters).filter(([, v]) => (Array.isArray(v) ? v.length : v)).length
  );

  async function load() {
    loading = true;
    error = '';
    try {
      const res = await fetchMissions($state.snapshot(filters), PAGE, page * PAGE);
      items = res.items;
      total = res.total;
    } catch (e) {
      error = e.message;
    } finally {
      loading = false;
    }
  }

  // Recarga al cambiar filtros o página (un filtro nuevo vuelve a la página 1),
  // y en vivo cuando llegan cambios de misiones por el WebSocket (máx. 1/s).
  let lastKey = '';
  let lastLoad = 0;
  let pendingTimer = null;
  let firstVersion = true;
  $effect(() => {
    const key = JSON.stringify(filters);
    if (key !== lastKey) {
      lastKey = key;
      if (page !== 0) {
        page = 0;   // vuelve a ejecutarse este efecto con la página 1
        return;
      }
    }
    page;
    lastLoad = Date.now();
    load();
  });
  $effect(() => {
    fleet.missionsVersion;
    if (firstVersion) {
      firstVersion = false;
      return;
    }
    clearTimeout(pendingTimer);
    const wait = Math.max(0, 1000 - (Date.now() - lastLoad));
    pendingTimer = setTimeout(() => {
      lastLoad = Date.now();
      load();
    }, wait);
    return () => clearTimeout(pendingTimer);
  });

  function toggleState(s) {
    filters.states = filters.states.includes(s)
      ? filters.states.filter((x) => x !== s)
      : [...filters.states, s];
  }

  function clearFilters() {
    filters = { ...EMPTY, states: [] };
  }

  function openRetry(m) {
    retrying = m;
    retryRobot = '';
    notice = '';
  }

  async function confirmRetry() {
    error = '';
    try {
      const nueva = await retryMission(retrying.id, retryRobot);
      notice = `Reenviada como ${nueva.id.slice(0, 8)}${retryRobot ? ` (solo ${retryRobot})` : ''}`;
      retrying = null;
    } catch (e) {
      error = e.message;
    }
  }

  // ------------------------------------------------------------ formato
  const fmtDate = (iso) =>
    new Date(iso).toLocaleString('es-ES', { day: '2-digit', month: '2-digit', hour: '2-digit',
                                           minute: '2-digit', second: '2-digit' });


  async function exportCsv() {
    // Exporta todos los resultados del filtro actual (hasta 500)
    const { items: all } = await fetchMissions($state.snapshot(filters), 500, 0);
    const cols = ['id', 'created_at', 'updated_at', 'origin', 'destination', 'priority', 'state',
                  'robot_id', 'reason', 'retry_of', 'preferred_robot'];
    const esc = (v) => `"${String(v ?? '').replaceAll('"', '""')}"`;
    const csv = [cols.join(';'), ...all.map((m) => cols.map((c) => esc(m[c])).join(';'))].join('\n');
    const url = URL.createObjectURL(new Blob(['﻿' + csv], { type: 'text/csv;charset=utf-8' }));
    const a = Object.assign(document.createElement('a'), { href: url, download: 'historial_ordenes.csv' });
    a.click();
    URL.revokeObjectURL(url);
  }
</script>

<div class="card filters">
  <div class="row head">
    <h2>Filtros {#if activeFilters}<span class="count">{activeFilters}</span>{/if}</h2>
    <div class="actions">
      <button onclick={clearFilters} disabled={!activeFilters}>Limpiar</button>
      <button onclick={exportCsv} disabled={!total}>Exportar CSV</button>
    </div>
  </div>

  <div class="states">
    {#each STATES as s}
      <button class="chip" class:on={filters.states.includes(s)}
              style="--c:{STATE_COLORS[s]}" onclick={() => toggleState(s)}>{s}</button>
    {/each}
  </div>

  <div class="grid">
    <label>Robot
      <select bind:value={filters.robot_id}>
        <option value="">Todos</option>
        {#each robots as r}<option value={r}>{r}</option>{/each}
      </select>
    </label>
    <label>Origen
      <select bind:value={filters.origin}>
        <option value="">Todos</option>
        {#each pickups as s}<option value={s.id}>{s.id}</option>{/each}
      </select>
    </label>
    <label>Destino
      <select bind:value={filters.destination}>
        <option value="">Todos</option>
        {#each drops as s}<option value={s.id}>{s.id}</option>{/each}
      </select>
    </label>
    <label>Prioridad
      <select bind:value={filters.priority}>
        <option value="">Todas</option>
        <option value="1">1 · alta</option>
        <option value="2">2 · media</option>
        <option value="3">3 · baja</option>
      </select>
    </label>
    <label>Desde
      <input type="datetime-local" bind:value={filters.created_from} />
    </label>
    <label>Hasta
      <input type="datetime-local" bind:value={filters.created_to} />
    </label>
    <label>Id de orden
      <input type="search" placeholder="p. ej. 3f2a" bind:value={filters.id_prefix} />
    </label>
  </div>
</div>

<div class="card">
  <div class="row head">
    <h2>Órdenes <span class="muted">· {total} resultado{total === 1 ? '' : 's'}</span></h2>
    {#if loading}<span class="muted small">Actualizando…</span>{/if}
  </div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
  {#if notice}<p class="notice" role="status">{notice}</p>{/if}

  {#if items.length === 0}
    <p class="muted">No hay órdenes con estos filtros.</p>
  {:else}
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Id</th><th>Creada</th><th>Ruta</th><th>Prio.</th><th>Estado</th>
            <th>Robot</th><th>Duración</th><th>Detalle</th><th></th>
          </tr>
        </thead>
        <tbody>
          {#each items as m (m.id)}
            <tr>
              <td class="mono">{m.id.slice(0, 8)}</td>
              <td class="nowrap">{fmtDate(m.created_at)}</td>
              <td class="nowrap"><strong>{m.origin} → {m.destination}</strong></td>
              <td><span class="prio p{m.priority}">P{m.priority}</span></td>
              <td><span class="badge" style="background:{STATE_COLORS[m.state]}">{m.state}</span></td>
              <td>
                {#if m.robot_id}
                  <button class="link" onclick={() => (filters.robot_id = m.robot_id)}
                          title="Filtrar por {m.robot_id}">{m.robot_id}</button>
                {:else if m.preferred_robot}
                  <span class="muted" title="Reservada para {m.preferred_robot}">→ {m.preferred_robot}</span>
                {:else}<span class="muted">—</span>{/if}
              </td>
              <td class="nowrap">{duration(m)}</td>
              <td class="detail">
                {#if m.reason}<em>{m.reason}</em>{/if}
                {#if m.retry_of}
                  <button class="link small" onclick={() => (filters.id_prefix = m.retry_of.slice(0, 8))}>
                    reintento de {m.retry_of.slice(0, 8)}
                  </button>
                {/if}
              </td>
              <td>
                {#if (m.state === 'FAILED' || m.state === 'CANCELLED') && isOperator()}
                  <button class="small" onclick={() => openRetry(m)}>Reenviar</button>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>

    <div class="pager">
      <button onclick={() => page--} disabled={page === 0}>← Anterior</button>
      <span class="muted">Página {page + 1} de {pages}</span>
      <button onclick={() => page++} disabled={page + 1 >= pages}>Siguiente →</button>
    </div>
  {/if}
</div>

{#if retrying}
  <div class="backdrop" role="presentation" onclick={() => (retrying = null)}></div>
  <div class="dialog card" role="dialog" aria-label="Reenviar orden">
    <h2>Reenviar orden {retrying.id.slice(0, 8)}</h2>
    <p><strong>{retrying.origin} → {retrying.destination}</strong> · P{retrying.priority}
      · estaba <span class="badge" style="background:{STATE_COLORS[retrying.state]}">{retrying.state}</span></p>
    {#if retrying.reason}<p class="muted small">Motivo: {retrying.reason}</p>{/if}
    <label>Robot
      <select bind:value={retryRobot}>
        <option value="">Cualquiera (el más cercano disponible)</option>
        {#each robots as r}<option value={r}>Solo {r}</option>{/each}
      </select>
    </label>
    <p class="muted small">Se crea una orden nueva enlazada a esta. La original no se modifica.</p>
    <div class="dialog-actions">
      <button onclick={() => (retrying = null)}>Cancelar</button>
      <button class="primary" onclick={confirmRetry}>Reenviar</button>
    </div>
  </div>
{/if}

<svelte:window
  onkeydown={(e) => e.key === 'Escape' && (retrying = null)}
  onhashchange={() => location.hash.includes('?') && (filters = filtersFromHash())} />

<style>
  .card + .card { margin-top: 16px; }
  .row { display: flex; justify-content: space-between; align-items: center; gap: 12px; }
  .head h2 { margin: 0; }
  .head { margin-bottom: 10px; }
  .actions { display: flex; gap: 8px; }
  .count { background: var(--brand-dark); color: #fff; border-radius: 999px; padding: 0 7px;
           font-size: 11px; margin-left: 4px; }

  .states { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
  .chip { font-size: 12px; padding: 3px 10px; border-radius: 999px; border-color: var(--c); color: var(--c); }
  .chip.on { background: var(--c); color: #fff; }

  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 10px; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }

  .table-wrap { overflow-x: auto; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; }
  th { text-align: left; font-size: 11px; text-transform: uppercase; letter-spacing: 0.04em;
       color: var(--muted); padding: 6px 8px; border-bottom: 2px solid var(--border); }
  td { padding: 7px 8px; border-bottom: 1px solid var(--border); vertical-align: middle; }
  tbody tr:hover { background: var(--brand-soft); }
  .nowrap { white-space: nowrap; }
  .detail { font-size: 12px; color: var(--muted); max-width: 260px; }
  .detail em + .link { margin-left: 6px; }

  .prio { font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; }
  .p1 { background: #f8e1e3; color: #a3313e; }
  .p2 { background: #fbefd9; color: #9a6418; }
  .p3 { background: #e1eef2; color: #2f6e80; }

  button.small { padding: 2px 8px; font-size: 12px; }
  button.link { border: none; background: none; padding: 0; color: var(--accent); text-decoration: underline; }
  .small { font-size: 12px; }
  .pager { display: flex; justify-content: center; align-items: center; gap: 14px; margin-top: 12px; }
  .error { color: var(--danger); }
  .notice { color: var(--brand-dark); background: var(--brand-soft); padding: 6px 10px; border-radius: 6px; }

  .backdrop { position: fixed; inset: 0; background: rgba(30, 59, 50, 0.35); z-index: 10; }
  .dialog { position: fixed; z-index: 11; top: 50%; left: 50%; transform: translate(-50%, -50%);
            width: min(420px, 92vw); box-shadow: 0 20px 50px rgba(30, 59, 50, 0.3); }
  .dialog h2 { text-transform: none; font-size: 15px; color: var(--text); }
  .dialog label { margin: 10px 0; }
  .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
