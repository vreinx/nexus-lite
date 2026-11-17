<script>
  // F-01: mapa 2D en SVG. Estaciones fijas + robots coloreados por estado.
  //
  // El SVG ocupa todo el hueco disponible y dibuja una cuadrícula "infinita".
  // La planta (la superficie por la que se mueven los robots) se escala y se
  // centra en la zona libre: la que no tapan los paneles flotantes (insets).
  import { fleet, ROBOT_COLORS, batteryColor, isOperator } from '../lib/fleet.svelte.js';
  import RobotIcon from './RobotIcon.svelte';
  import MissionPopover from './MissionPopover.svelte';
  import PalletIcon from './PalletIcon.svelte';
  import { nextHeading, routeCells } from '../lib/logic.js';

  const C = 40;      // píxeles por celda
  const MARGIN = 14; // margen alrededor del mapa para que no se corten los robots del borde

  const STATION_STYLE = {
    PICKUP: { fill: '#e1eef2', stroke: '#4a90a4' },
    DROP: { fill: '#e7f1ec', stroke: '#3e7560' },
    CHARGER: { fill: '#fbf0dc', stroke: '#c98a2e' },
    PARKING: { fill: '#eef2f0', stroke: '#8a9a93', dash: '3 3', small: true },
  };

  const LEGEND_H = 30; // hueco reservado abajo para la leyenda

  // Píxeles que ocupan los paneles flotantes a cada lado (los pasa App.svelte)
  let { insets = {} } = $props();

  let map = $derived(fleet.map);
  let width = $derived(map.grid.width * C);
  let height = $derived(map.grid.height * C);

  // Tamaño en píxeles del contenedor
  let boxW = $state(0);
  let boxH = $state(0);
  let left = $derived(insets.left ?? 0);
  let right = $derived(insets.right ?? 0);

  // Parte visible del plano (viewBox) y escala s (píxeles por unidad del SVG).
  // La planta más su margen cabe entera en la zona libre y queda centrada en ella.
  let view = $derived.by(() => {
    const w = width + 2 * MARGIN, h = height + 2 * MARGIN;
    if (!boxW || !boxH) return { x: -MARGIN, y: -MARGIN, w, h, s: 1 };
    const top = insets.top ?? 0, bottom = (insets.bottom ?? 0) + LEGEND_H;
    const freeW = Math.max(boxW - left - right, 80);
    const freeH = Math.max(boxH - top - bottom, 80);
    const s = Math.min(freeW / w, freeH / h);
    return {
      s,
      w: boxW / s,
      h: boxH / s,
      x: -(left + (freeW - width * s) / 2) / s,
      y: -(top + (freeH - height * s) / 2) / s,
    };
  });
  // De coordenadas del SVG a píxeles del contenedor
  const px = (x) => (x - view.x) * view.s;
  const py = (y) => (y - view.y) * view.s;

  // Orientación de cada robot: hacia su siguiente celda (ver logic.js)
  // Se recuerda la última posición vista de cada robot para saber hacia dónde
  // se acaba de mover. Si el robot no ha cambiado (la lista se recalcula por
  // otro robot), se devuelve la orientación que ya tenía.
  const headings = {};
  const heading = (r) => {
    const key = `${r.x},${r.y},${r.state},${r.target},${r.path?.[0]}`;
    const last = headings[r.id];
    if (last?.key === key) return last.angle;
    const angle = nextHeading(last?.angle ?? -90, r, last?.pos);
    headings[r.id] = { key, angle, pos: [r.x, r.y] };
    return angle;
  };

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

  // Celdas que ocupa una estación: una, o una por plaza si es un cargador
  const cellsOf = (s) => (s.bays?.length ? s.bays : [{ x: s.x, y: s.y }]);

  // Crear orden haciendo clic en una estación de recogida
  let picker = $state(null);
  let pickerStyle = $derived.by(() => {
    if (!picker) return '';
    // Se abre al lado contrario del borde más cercano para no salirse del mapa
    const side = picker.x < map.grid.width / 2
      ? `left: ${px((picker.x + 1) * C) + 6}px;`
      : `right: ${boxW - px(picker.x * C) + 6}px;`;
    const vertical = picker.y > map.grid.height / 2
      ? `bottom: ${boxH - py((picker.y + 1) * C)}px;`
      : `top: ${py(picker.y * C)}px;`;
    return side + vertical;
  });
  const openPicker = (s) => (picker = picker?.id === s.id ? null : s);
  const select = (id) => (fleet.selectedRobot = fleet.selectedRobot === id ? null : id);
</script>

<div class="wrap" class:frozen={fleet.connection !== 'online'}
     bind:clientWidth={boxW} bind:clientHeight={boxH}>
  <svg viewBox="{view.x} {view.y} {view.w} {view.h}" role="img" aria-label="Mapa de la planta">
    <defs>
      <!-- Una celda de la cuadrícula; las líneas caen en los bordes de celda -->
      <pattern id="floor-grid" x={C / 2} y={C / 2} width={C} height={C} patternUnits="userSpaceOnUse">
        <path d="M {C / 2} 0 V {C} M 0 {C / 2} H {C}" class="grid" />
      </pattern>
    </defs>
    <!-- Fondo "infinito" y, encima, la superficie de la planta -->
    <rect x={view.x} y={view.y} width={view.w} height={view.h} class="outside"
          onclick={() => (picker = null)} role="presentation" />
    <rect x="0" y="0" {width} {height} class="floor" onclick={() => (picker = null)} role="presentation" />
    <rect x={view.x} y={view.y} width={view.w} height={view.h} fill="url(#floor-grid)" pointer-events="none" />
    <rect x="0" y="0" {width} {height} class="floor-edge" pointer-events="none" />

    <!-- Estaciones -->
    {#each map.stations as s}
      {@const st = STATION_STYLE[s.type]}
      {#if s.queue}
        <rect x={s.queue.x * C + 3} y={s.queue.y * C + 3} width={C - 6} height={C - 6}
              rx="4" fill="none" stroke={st.stroke} stroke-dasharray="4 3" />
        <text x={center(s.queue.x)} y={center(s.queue.y) + 4} class="queue-label">cola</text>
      {/if}
      {#if s.type === 'PICKUP' && isOperator()}
        <rect x={s.x * C + 2} y={s.y * C + 2} width={C - 4} height={C - 4} rx="5"
              fill={st.fill} stroke={st.stroke} stroke-width={picker?.id === s.id ? 3.5 : 2}
              class="clickable" role="button" tabindex="0"
              aria-label="Crear orden desde {s.id}"
              onclick={() => openPicker(s)}
              onkeydown={(e) => e.key === 'Enter' && openPicker(s)}>
          <title>Clic para crear una orden desde {s.id}</title>
        </rect>
      {:else}
        {#each cellsOf(s) as c}
          <rect x={c.x * C + 2} y={c.y * C + 2} width={C - 4} height={C - 4} rx="5"
                fill={st.fill} stroke={st.stroke} stroke-width="2" stroke-dasharray={st.dash ?? 'none'} />
        {/each}
      {/if}
      {@const load = fleet.stations[s.id]}
      {#if load?.pallet}
        <!-- con palet: etiqueta pequeña arriba y el palet debajo -->
        <text x={center(s.x)} y={s.y * C + 11} class="station-label tiny" pointer-events="none"
              fill={st.stroke}>{s.id}</text>
        <g transform="translate({center(s.x)}, {center(s.y) + 4}) scale(0.95)">
          {#key load.since}
            <PalletIcon timer={load.clears_in ? map.simulation.drop_clear_seconds : 0}
                        reserved={!!load.reserved_by} />
          {/key}
        </g>
      {:else}
        {#each cellsOf(s) as c}
          <text x={center(c.x)} y={center(c.y) + 4} class="station-label" class:small={st.small}
                pointer-events="none" fill={st.stroke}>{s.id}</text>
        {/each}
      {/if}
    {/each}

    <!-- Ruta hasta el destino: la calculada con A* en el backend -->
    {#each robots as r (r.id)}
      {#if r.target}
        <polyline points={routeCells(r).map(([x, y]) => `${center(x)},${center(y)}`).join(' ')}
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
          <RobotIcon state={r.state} angle={r.angle}
                     loaded={['LOADING', 'TO_DROP', 'UNLOADING'].includes(r.state) ||
                             (!!r.mission_id && ['ERROR', 'TO_CHARGER', 'CHARGING'].includes(r.state))} />
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
    <div class="overlay" style="left: {left + (boxW - left - right) / 2}px">Sin conexión en tiempo real: el mapa puede no estar actualizado</div>
  {/if}

  <div class="legend" style="left: {left}px; right: {right}px">
    {#each Object.entries(ROBOT_COLORS) as [state, color]}
      <span><i style="background:{color}"></i>{state}</span>
    {/each}
  </div>
</div>

<style>
  .wrap { position: absolute; inset: 0; overflow: hidden; }
  svg { width: 100%; height: 100%; display: block; }
  .outside { fill: #eef2f0; }
  .floor { fill: #fcfdfc; }
  .floor-edge { fill: none; stroke: #9db3a8; stroke-width: 1.5; }
  .frozen svg { filter: grayscale(0.7); opacity: 0.7; }
  .grid { fill: none; stroke: #dde6e1; stroke-width: 1; }
  .station-label { font-size: 13px; font-weight: 700; text-anchor: middle; }
  .station-label.small { font-size: 10px; }
  .station-label.tiny { font-size: 9px; }
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
    position: absolute; top: 10px; transform: translateX(-50%); white-space: nowrap;
    background: #c2414f; color: #fff; padding: 6px 14px; border-radius: 6px; font-size: 13px;
  }
  .legend { position: absolute; bottom: 8px; display: flex; flex-wrap: wrap; justify-content: center;
            gap: 4px 12px; font-size: 11px; color: var(--muted); pointer-events: none; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; vertical-align: -1px; }
</style>
