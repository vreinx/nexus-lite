<script>
  // Histórico de batería de un robot (InfluxDB), últimos 10 minutos. Se refresca
  // cada 5 s. Eje Y fijo 0–100 % y líneas en los umbrales de carga (20 %) y
  // de asignación (30 %).
  import { fleet, fetchTelemetry } from '../lib/fleet.svelte.js';
  import { batteryPath } from '../lib/logic.js';

  let { robotId } = $props();

  const W = 320, H = 90;
  let points = $state([]);
  let error = $state('');

  let low = $derived(fleet.map?.simulation.low_battery_threshold ?? 20);
  let assign = $derived(fleet.map?.simulation.min_battery_to_assign ?? 30);
  let paths = $derived(batteryPath(points, W, H));
  let first = $derived(points[0] ? new Date(points[0].time) : null);
  const y = (pct) => H - (pct / 100) * H;
  const hhmm = (d) => d.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });

  async function load(id) {
    try {
      points = await fetchTelemetry(id, 10, 5);
      error = '';
    } catch (e) {
      error = e.message;
    }
  }

  $effect(() => {
    const id = robotId;
    points = [];
    load(id);
    const timer = setInterval(() => load(id), 5000);
    return () => clearInterval(timer);
  });
</script>

<div class="chart">
  <div class="title">Batería · últimos 10 min</div>
  {#if error}
    <p class="muted small">Histórico no disponible: {error}</p>
  {:else if points.length < 2}
    <p class="muted small">Recogiendo datos…</p>
  {:else}
    <svg viewBox="-28 -6 {W + 34} {H + 22}" role="img" aria-label="Histórico de batería de {robotId}">
      {#each [0, 50, 100] as pct}
        <line x1="0" x2={W} y1={y(pct)} y2={y(pct)} class="grid" />
        <text x="-6" y={y(pct) + 3} class="axis" text-anchor="end">{pct}%</text>
      {/each}
      <line x1="0" x2={W} y1={y(assign)} y2={y(assign)} class="thr assign" />
      <line x1="0" x2={W} y1={y(low)} y2={y(low)} class="thr low" />
      <path d={paths.area} class="area" />
      <path d={paths.line} class="line" />
      <text x="0" y={H + 14} class="axis">{hhmm(first)}</text>
      <text x={W} y={H + 14} class="axis" text-anchor="end">ahora</text>
    </svg>
    <div class="legend">
      <span><i class="l-assign"></i>{assign} % mínimo para órdenes</span>
      <span><i class="l-low"></i>{low} % va a cargar</span>
    </div>
  {/if}
</div>

<style>
  .chart { margin-top: 14px; padding-top: 12px; border-top: 1px solid var(--border); }
  .title { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
  svg { width: 100%; height: auto; display: block; }
  .grid { stroke: #e3eae6; stroke-width: 1; }
  .axis { font-size: 9px; fill: var(--muted); }
  .thr { stroke-width: 1; stroke-dasharray: 4 3; }
  .thr.assign { stroke: #e0a458; }
  .thr.low { stroke: #d1495b; }
  .area { fill: rgba(108, 160, 135, 0.18); }
  .line { fill: none; stroke: #3e7560; stroke-width: 2; stroke-linejoin: round; }
  .legend { display: flex; gap: 14px; font-size: 11px; color: var(--muted); margin-top: 4px; }
  .legend i { display: inline-block; width: 12px; border-top: 2px dashed; margin-right: 4px; vertical-align: middle; }
  .l-assign { border-color: #e0a458; }
  .l-low { border-color: #d1495b; }
  .small { font-size: 12px; }
</style>
