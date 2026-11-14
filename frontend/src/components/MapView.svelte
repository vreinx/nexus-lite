<script>
  // F-01: mapa 2D en SVG. Estaciones fijas + robots coloreados por estado.
  import { fleet, ROBOT_COLORS } from '../lib/fleet.svelte.js';

  const C = 40; // píxeles por celda

  const STATION_STYLE = {
    PICKUP: { fill: '#dbeafe', stroke: '#3b82f6' },
    DROP: { fill: '#dcfce7', stroke: '#16a34a' },
    CHARGER: { fill: '#fef9c3', stroke: '#ca8a04' },
  };

  let map = $derived(fleet.map);
  let width = $derived(map.grid.width * C);
  let height = $derived(map.grid.height * C);

  // Si varios robots comparten celda, se separan un poco para que se vean todos.
  let robots = $derived.by(() => {
    const list = Object.values(fleet.robots).sort((a, b) => a.id.localeCompare(b.id));
    const byCell = {};
    for (const r of list) (byCell[`${r.x},${r.y}`] ??= []).push(r);
    return list.map((r) => {
      const group = byCell[`${r.x},${r.y}`];
      const i = group.indexOf(r);
      const offset = (i - (group.length - 1) / 2) * 9;
      return { ...r, px: r.x * C + C / 2 + offset, py: r.y * C + C / 2 };
    });
  });

  const center = (x) => x * C + C / 2;
  const select = (id) => (fleet.selectedRobot = fleet.selectedRobot === id ? null : id);
</script>

<div class="wrap" class:frozen={fleet.connection !== 'online'}>
  <svg viewBox="0 0 {width} {height}" role="img" aria-label="Mapa de la planta">
    <!-- Cuadrícula -->
    {#each { length: map.grid.width + 1 } as _, i}
      <line x1={i * C} y1="0" x2={i * C} y2={height} class="grid" />
    {/each}
    {#each { length: map.grid.height + 1 } as _, j}
      <line x1="0" y1={j * C} x2={width} y2={j * C} class="grid" />
    {/each}

    <!-- Estaciones -->
    {#each map.stations as s}
      {@const st = STATION_STYLE[s.type]}
      {#if s.queue}
        <rect x={s.queue.x * C + 3} y={s.queue.y * C + 3} width={C - 6} height={C - 6}
              rx="4" fill="none" stroke={st.stroke} stroke-dasharray="4 3" />
        <text x={center(s.queue.x)} y={center(s.queue.y) + 4} class="queue-label">cola</text>
      {/if}
      <rect x={s.x * C + 2} y={s.y * C + 2} width={C - 4} height={C - 4} rx="5"
            fill={st.fill} stroke={st.stroke} stroke-width="2" />
      <text x={center(s.x)} y={center(s.y) + 4} class="station-label" fill={st.stroke}>{s.id}</text>
    {/each}

    <!-- Ruta hasta el destino: en L, primero X y luego Y, como se mueve el robot -->
    {#each robots as r (r.id)}
      {#if r.target}
        <polyline points="{center(r.x)},{center(r.y)} {center(r.target[0])},{center(r.y)} {center(r.target[0])},{center(r.target[1])}"
              fill="none" stroke={ROBOT_COLORS[r.state]} stroke-width="2" stroke-dasharray="5 4" opacity="0.6" />
      {/if}
    {/each}

    <!-- Robots -->
    {#each robots as r (r.id)}
      <g class="robot" class:selected={fleet.selectedRobot === r.id}
         style="transform: translate({r.px}px, {r.py}px)"
         onclick={() => select(r.id)} role="button" tabindex="0"
         onkeydown={(e) => e.key === 'Enter' && select(r.id)}>
        <title>{r.id} · {r.state} · {r.battery}%</title>
        <circle r="14" fill={ROBOT_COLORS[r.state]} class="body" />
        <text y="4" class="robot-label">{r.id}</text>
        <rect x="-13" y="17" width="26" height="4" rx="2" fill="#e2e8f0" />
        <rect x="-13" y="17" width={26 * r.battery / 100} height="4" rx="2"
              fill={r.battery < 20 ? '#ef4444' : r.battery < 30 ? '#f59e0b' : '#22c55e'} />
      </g>
    {/each}
  </svg>

  {#if fleet.connection !== 'online'}
    <div class="overlay">Sin conexión en tiempo real: el mapa puede no estar actualizado</div>
  {/if}
</div>

<div class="legend">
  {#each Object.entries(ROBOT_COLORS) as [state, color]}
    <span><i style="background:{color}"></i>{state}</span>
  {/each}
</div>

<style>
  .wrap { position: relative; }
  svg { width: 100%; height: auto; display: block; background: #f8fafc; border-radius: 6px; }
  .frozen svg { filter: grayscale(0.7); opacity: 0.7; }
  .grid { stroke: #e2e8f0; stroke-width: 1; }
  .station-label { font-size: 13px; font-weight: 700; text-anchor: middle; }
  .queue-label { font-size: 10px; text-anchor: middle; fill: #a16207; }

  /* El simulador avanza 1 celda/s: la transición de 1 s hace el movimiento continuo */
  .robot { cursor: pointer; transition: transform 1s linear; }
  .robot .body { stroke: #fff; stroke-width: 2; }
  .robot.selected .body { stroke: #0f172a; stroke-width: 3; }
  .robot-label { font-size: 10px; font-weight: 700; text-anchor: middle; fill: #fff; pointer-events: none; }

  .overlay {
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    background: #dc2626; color: #fff; padding: 6px 14px; border-radius: 6px; font-size: 13px;
  }
  .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 11px; color: var(--muted); }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
</style>
