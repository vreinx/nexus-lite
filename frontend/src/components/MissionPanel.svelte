<script>
  // F-02: lista de misiones en vivo, formulario para crear y botón para cancelar.
  import { fleet, createMission, cancelMission } from '../lib/fleet.svelte.js';

  const MISSION_COLORS = {
    PENDING: '#8a9a93',
    ASSIGNED: '#4a90a4',
    IN_PROGRESS: '#d4903f',
    DONE: '#4f9a77',
    CANCELLED: '#b3bdb8',
    FAILED: '#c2414f',
  };
  const ACTIVE = ['PENDING', 'ASSIGNED', 'IN_PROGRESS'];
  const CANCELLABLE = ['PENDING', 'ASSIGNED'];

  let pickups = $derived(fleet.map?.stations.filter((s) => s.type === 'PICKUP') ?? []);
  let drops = $derived(fleet.map?.stations.filter((s) => s.type === 'DROP') ?? []);

  let origin = $state('P1');
  let destination = $state('D1');
  let priority = $state(2);
  let filter = $state('ACTIVE');
  let robotFilter = $state('');
  let robotIds = $derived(Object.keys(fleet.robots).sort());
  let error = $state('');
  let sending = $state(false);

  let missions = $derived.by(() => {
    let list = Object.values(fleet.missions);
    if (filter === 'ACTIVE') list = list.filter((m) => ACTIVE.includes(m.state));
    else if (filter !== 'ALL') list = list.filter((m) => m.state === filter);
    if (robotFilter) list = list.filter((m) => m.robot_id === robotFilter || m.preferred_robot === robotFilter);
    // Activas: por prioridad y antigüedad (el orden en que se asignan). Resto: más recientes primero.
    return list.sort((a, b) => {
      const aa = ACTIVE.includes(a.state), ba = ACTIVE.includes(b.state);
      if (aa !== ba) return aa ? -1 : 1;
      if (aa) return a.priority - b.priority || a.created_at.localeCompare(b.created_at);
      return b.created_at.localeCompare(a.created_at);
    });
  });

  let counts = $derived.by(() => {
    const c = {};
    for (const m of Object.values(fleet.missions)) c[m.state] = (c[m.state] ?? 0) + 1;
    return c;
  });

  async function submit(e) {
    e.preventDefault();
    error = '';
    sending = true;
    try {
      await createMission(origin, destination, Number(priority));
    } catch (err) {
      error = err.message;
    } finally {
      sending = false;
    }
  }

  async function cancel(id) {
    error = '';
    try {
      await cancelMission(id);
    } catch (err) {
      error = err.message;
    }
  }

  const time = (iso) => new Date(iso).toLocaleTimeString('es-ES');
</script>

<div class="card">
  <h2>Nueva misión</h2>
  <form onsubmit={submit}>
    <label>Origen
      <select bind:value={origin}>
        {#each pickups as s}<option value={s.id}>{s.id}</option>{/each}
      </select>
    </label>
    <label>Destino
      <select bind:value={destination}>
        {#each drops as s}<option value={s.id}>{s.id}</option>{/each}
      </select>
    </label>
    <label>Prioridad
      <select bind:value={priority}>
        <option value={1}>1 · alta</option>
        <option value={2}>2 · media</option>
        <option value={3}>3 · baja</option>
      </select>
    </label>
    <button class="primary" type="submit" disabled={sending}>Crear</button>
  </form>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</div>

<div class="card">
  <div class="list-head">
    <h2>Misiones</h2>
    <select bind:value={robotFilter} aria-label="Filtrar por robot">
      <option value="">Todos los robots</option>
      {#each robotIds as r}<option value={r}>{r}</option>{/each}
    </select>
    <select bind:value={filter} aria-label="Filtrar misiones">
      <option value="ACTIVE">Activas</option>
      <option value="ALL">Todas</option>
      {#each Object.keys(MISSION_COLORS) as s}
        <option value={s}>{s} ({counts[s] ?? 0})</option>
      {/each}
    </select>
  </div>

  {#if missions.length === 0}
    <p class="muted">No hay misiones{filter === 'ACTIVE' ? ' activas' : ''}{robotFilter ? ` de ${robotFilter}` : ''}.</p>
  {:else}
    <ul>
      {#each missions as m (m.id)}
        <li>
          <div class="row">
            <span class="prio p{m.priority}" title="Prioridad {m.priority}">P{m.priority}</span>
            <strong>{m.origin} → {m.destination}</strong>
            <span class="badge" style="background:{MISSION_COLORS[m.state]}">{m.state}</span>
            {#if CANCELLABLE.includes(m.state)}
              <button class="danger small" onclick={() => cancel(m.id)}>Cancelar</button>
            {/if}
          </div>
          <div class="meta muted">
            <span class="mono">{m.id.slice(0, 8)}</span>
            · {time(m.created_at)}
            {#if m.robot_id}
              · <button class="link" onclick={() => (fleet.selectedRobot = m.robot_id)}>{m.robot_id}</button>
            {/if}
            {#if m.reason}· <em>{m.reason}</em>{/if}
          </div>
        </li>
      {/each}
    </ul>
  {/if}
</div>

<style>
  form { display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 8px; align-items: end; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  .error { color: var(--danger); margin: 10px 0 0; font-size: 13px; }

  .list-head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .list-head h2 { margin: 0; margin-right: auto; }
  .list-head { gap: 6px; }
  ul { list-style: none; margin: 0; padding: 0; max-height: 460px; overflow-y: auto; }
  li { padding: 8px 0; border-top: 1px solid var(--border); }
  .row { display: flex; align-items: center; gap: 8px; }
  .row strong { flex: 1; }
  .meta { font-size: 12px; margin-top: 3px; }
  .prio { font-size: 11px; font-weight: 700; padding: 1px 6px; border-radius: 4px; }
  .p1 { background: #f8e1e3; color: #a3313e; }
  .p2 { background: #fbefd9; color: #9a6418; }
  .p3 { background: #e1eef2; color: #2f6e80; }
  button.small { padding: 2px 8px; font-size: 12px; }
  button.link { border: none; background: none; padding: 0; color: var(--accent); text-decoration: underline; }
</style>
