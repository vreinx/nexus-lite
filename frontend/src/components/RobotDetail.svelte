<script>
  // F-03: detalle del robot seleccionado (estado, batería y misión actual).
  import { fleet, ROBOT_COLORS, batteryColor } from '../lib/fleet.svelte.js';

  let robot = $derived(fleet.selectedRobot ? fleet.robots[fleet.selectedRobot] : null);
  let mission = $derived(robot?.mission_id ? fleet.missions[robot.mission_id] : null);

  // Nombre de la estación en una celda (para mostrar "PK2", "C1", "P3"...)
  const stationAt = (x, y) =>
    fleet.map?.stations.find((s) => (s.bays?.length ? s.bays : [s]).some((c) => c.x === x && c.y === y))?.id
    ?? (fleet.map?.stations.some((s) => s.queue?.x === x && s.queue?.y === y) ? 'cola C1' : undefined);
  let here = $derived(robot ? stationAt(robot.x, robot.y) : null);
  let goingTo = $derived(robot?.target ? stationAt(robot.target[0], robot.target[1]) : null);

  // Va a cargar pero su destino no es una plaza de C1: está esperando turno (cola o parking)
  let bays = $derived(fleet.map?.stations.find((s) => s.type === 'CHARGER')?.bays ?? []);
  let waitingCharge = $derived(
    robot?.state === 'TO_CHARGER' && robot.target &&
    !bays.some((b) => b.x === robot.target[0] && b.y === robot.target[1])
  );
</script>

<div class="card">
  <h2>Detalle de robot</h2>
  {#if !robot}
    <p class="muted">Haz clic en un robot del mapa o de la flota.</p>
  {:else}
    <div class="head">
      <strong class="id">{robot.id}</strong>
      <span class="badge" style="background:{ROBOT_COLORS[robot.state]}">{robot.state}</span>
      {#if waitingCharge}<span class="waiting">Esperando turno de carga</span>
      {:else if robot.waiting}<span class="waiting">Cediendo el paso</span>{/if}
    </div>

    <dl>
      <dt>Batería</dt>
      <dd>
        <div class="bar"><div style="width:{robot.battery}%;background:{batteryColor(robot.battery)}"></div></div>
        <span class="mono">{robot.battery}%</span>
      </dd>
      <dt>Posición</dt>
      <dd><span class="mono">({robot.x}, {robot.y})</span>{#if here}<span class="tag">{here}</span>{/if}</dd>
      <dt>Destino</dt>
      <dd>
        <span class="mono">{robot.target ? `(${robot.target[0]}, ${robot.target[1]})` : '—'}</span>
        {#if goingTo}<span class="tag">{goingTo}</span>{/if}
      </dd>
      <dt>Misión</dt>
      <dd>
        {#if mission}
          <span class="mono">{mission.id.slice(0, 8)}</span> ·
          {mission.origin} → {mission.destination} · P{mission.priority} · {mission.state}
        {:else if robot.mission_id}
          <span class="mono">{robot.mission_id.slice(0, 8)}</span>
        {:else}
          <span class="muted">Sin misión</span>
        {/if}
      </dd>
    </dl>
    <a class="history" href="#/historial?robot_id={robot.id}">Ver órdenes de {robot.id} →</a>
  {/if}
</div>

<style>
  .head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .id { font-size: 20px; }
  dl { display: grid; grid-template-columns: 80px 1fr; gap: 8px 12px; margin: 0; }
  dt { color: var(--muted); }
  dd { margin: 0; display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
  .waiting { font-size: 12px; font-weight: 600; color: #9a6418; background: #fbefd9;
             padding: 2px 8px; border-radius: 999px; }
  .history { display: inline-block; margin-top: 12px; font-size: 13px; color: var(--accent); font-weight: 600; }
  .tag { font-size: 11px; font-weight: 600; padding: 1px 6px; border-radius: 4px;
         background: var(--brand-soft); color: var(--brand-dark); }
  .bar { flex: 1; min-width: 120px; height: 8px; background: #e3eae6; border-radius: 4px; overflow: hidden; }
  .bar div { height: 100%; transition: width 1s linear; }
</style>
