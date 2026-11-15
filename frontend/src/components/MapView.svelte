<script>
  // F-01: mapa 2D en SVG. Estaciones fijas + robots coloreados por estado.
  import { fleet, ROBOT_COLORS, batteryColor } from '../lib/fleet.svelte.js';
  import RobotIcon from './RobotIcon.svelte';
  import MissionPopover from './MissionPopover.svelte';

  const C = 40;      // píxeles por celda
  const MARGIN = 14; // margen alrededor del mapa para que no se corten los robots del borde

  const STATION_STYLE = {
    PICKUP: { fill: '#e1eef2', stroke: '#4a90a4' },
    DROP: { fill: '#e7f1ec', stroke: '#3e7560' },
    CHARGER: { fill: '#fbf0dc', stroke: '#c98a2e' },
    PARKING: { fill: '#eef2f0', stroke: '#8a9a93', dash: '3 3', small: true },
  };

  let map = $derived(fleet.map);
  let width = $derived(map.grid.width * C);
  let height = $derived(map.grid.height * C);

  // Orientación de cada robot: hacia donde va a moverse (primero X, luego Y,
  // igual que el simulador). Si está parado conserva la última. Se acumula el
  // ángulo por el camino más corto para que no dé la vuelta entera al girar.
  const headings = {};
  function heading(r) {
    let target = null;
    if (r.target) {
      const [tx, ty] = r.target;
      if (r.x !== tx) target = tx > r.x ? 0 : 180;
      else if (r.y !== ty) target = ty > r.y ? 90 : -90;
    }
    const prev = headings[r.id] ?? -90; // al arrancar, mirando "hacia arriba"
    if (target === null) return prev;
    const delta = ((((target - prev) % 360) + 540) % 360) - 180;
    return (headings[r.id] = prev + delta);
  }

  // Si varios robots comparten celda, se separan y se encogen un poco para que se vean todos.
  let robots = $derived.by(() => {
    const list = Object.values(fleet.robots).sort((a, b) => a.id.localeCompare(b.id));
    const byCell = {};
    for (const r of list) (byCell[`${r.x},${r.y}`] ??= []).push(r);
    return list.map((r) => {
      const group = byCell[`${r.x},${r.y}`];
      const i = group.indexOf(r);
      const offset = (i - (group.length - 1) / 2) * 12;
      const scale = group.length > 1 ? 0.75 : 1;
      return { ...r, px: r.x * C + C / 2 + offset, py: r.y * C + C / 2, scale, angle: heading(r) };
    });
  });

  const center = (x) => x * C + C / 2;

  // Rectángulo de una estación: una celda, o varias contiguas si es un cargador con plazas
  function box(s) {
    const cells = s.bays?.length ? s.bays : [{ x: s.x, y: s.y }];
    const xs = cells.map((c) => c.x), ys = cells.map((c) => c.y);
    const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
    return { x: x0 * C + 2, y: y0 * C + 2, w: (x1 - x0 + 1) * C - 4, h: (y1 - y0 + 1) * C - 4,
             cx: ((x0 + x1 + 1) / 2) * C, cy: ((y0 + y1 + 1) / 2) * C };
  }

  // Crear orden haciendo clic en una estación de recogida
  let picker = $state(null);
  let pickerStyle = $derived.by(() => {
    if (!picker) return '';
    const W = width + 2 * MARGIN, H = height + 2 * MARGIN;
    const top = ((picker.y * C + MARGIN) / H) * 100;
    // Se abre al lado contrario del borde más cercano para no salirse del mapa
    const side = picker.x < map.grid.width / 2
      ? `left: ${(((picker.x + 1) * C + MARGIN + 6) / W) * 100}%;`
      : `right: ${((W - (picker.x * C + MARGIN) + 6) / W) * 100}%;`;
    const vertical = picker.y > map.grid.height / 2
      ? `bottom: ${100 - ((picker.y + 1) * C + MARGIN) / H * 100}%;`
      : `top: ${top}%;`;
    return side + vertical;
  });
  const openPicker = (s) => (picker = picker?.id === s.id ? null : s);
  const select = (id) => (fleet.selectedRobot = fleet.selectedRobot === id ? null : id);
</script>

<div class="wrap" class:frozen={fleet.connection !== 'online'}>
  <svg viewBox="{-MARGIN} {-MARGIN} {width + 2 * MARGIN} {height + 2 * MARGIN}" role="img" aria-label="Mapa de la planta">
    <rect x="0" y="0" {width} {height} class="floor" onclick={() => (picker = null)} role="presentation" />
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
      {@const b = box(s)}
      {#if s.queue}
        <rect x={s.queue.x * C + 3} y={s.queue.y * C + 3} width={C - 6} height={C - 6}
              rx="4" fill="none" stroke={st.stroke} stroke-dasharray="4 3" />
        <text x={center(s.queue.x)} y={center(s.queue.y) + 4} class="queue-label">cola</text>
      {/if}
      {#if s.type === 'PICKUP'}
        <rect x={s.x * C + 2} y={s.y * C + 2} width={C - 4} height={C - 4} rx="5"
              fill={st.fill} stroke={st.stroke} stroke-width={picker?.id === s.id ? 3.5 : 2}
              class="clickable" role="button" tabindex="0"
              aria-label="Crear orden desde {s.id}"
              onclick={() => openPicker(s)}
              onkeydown={(e) => e.key === 'Enter' && openPicker(s)}>
          <title>Clic para crear una orden desde {s.id}</title>
        </rect>
      {:else}
        <rect x={b.x} y={b.y} width={b.w} height={b.h} rx="5"
              fill={st.fill} stroke={st.stroke} stroke-width="2" stroke-dasharray={st.dash ?? 'none'} />
        {#if s.bays?.length > 1}
          {#each s.bays.slice(1) as bay}
            <line x1={bay.x * C} y1={b.y + 5} x2={bay.x * C} y2={b.y + b.h - 5}
                  stroke={st.stroke} stroke-width="1" stroke-dasharray="3 3" opacity="0.6" />
          {/each}
        {/if}
      {/if}
      <text x={b.cx} y={b.cy + 4} class="station-label" class:small={st.small}
            pointer-events="none"
            fill={st.stroke}>{s.id}</text>
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
        <g style="transform: scale({r.scale})" class="scaler">
          {#if fleet.selectedRobot === r.id}
            <circle r="21" class="halo" />
          {/if}
          <RobotIcon state={r.state} angle={r.angle} />
          <!-- etiqueta y batería no giran: siempre legibles -->
          <rect x="-11" y="-27" width="22" height="11" rx="5.5" fill={r.waiting ? '#d4903f' : '#1e3b32'} opacity="0.9" />
          <text y="-18.5" class="robot-label">{r.id}</text>
          <rect x="-12" y="17" width="24" height="3.5" rx="1.75" fill="#dce5e0" />
          <rect x="-12" y="17" width={24 * r.battery / 100} height="3.5" rx="1.75"
                fill={batteryColor(r.battery)} />
        </g>
      </g>
    {/each}
  </svg>

  {#if picker}
    <MissionPopover station={picker} style={pickerStyle} onclose={() => (picker = null)} />
  {/if}

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
  svg { width: 100%; height: auto; display: block; }
  .floor { fill: #fafcfb; }
  .frozen svg { filter: grayscale(0.7); opacity: 0.7; }
  .grid { stroke: #e3eae6; stroke-width: 1; }
  .station-label { font-size: 13px; font-weight: 700; text-anchor: middle; }
  .station-label.small { font-size: 10px; }
  .clickable { cursor: pointer; transition: stroke-width 0.15s; outline: none; }
  .clickable:hover { stroke-width: 3.5; filter: brightness(0.97); }
  .queue-label { font-size: 10px; text-anchor: middle; fill: #a06a1e; }

  /* El simulador avanza 1 celda/s: la transición de 1 s hace el movimiento continuo */
  .robot { cursor: pointer; transition: transform 1s linear; outline: none; }
  .scaler { transition: transform 0.3s; }
  .halo { fill: rgba(108, 160, 135, 0.18); stroke: #3e7560; stroke-width: 2; stroke-dasharray: 4 3;
          animation: spin 6s linear infinite; }
  .robot-label { font-size: 8px; font-weight: 700; text-anchor: middle; fill: #fff; pointer-events: none; }
  @keyframes spin { to { transform: rotate(360deg); } }

  .overlay {
    position: absolute; top: 10px; left: 50%; transform: translateX(-50%);
    background: #c2414f; color: #fff; padding: 6px 14px; border-radius: 6px; font-size: 13px;
  }
  .legend { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; font-size: 11px; color: var(--muted); }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
</style>
