<script>
  // AMR visto desde arriba. Dibujado mirando hacia +X (derecha); MapView lo
  // gira según la dirección en la que se mueve.
  //
  // El frente se reconoce por la barra de sensores (LiDAR) y los pilotos.
  // Lomo según estado:
  //   - Caja de mercancía cuando transporta (LOADING, TO_DROP, UNLOADING).
  //   - CHARGING: rayo.   - ERROR: triángulo de aviso y parpadeo.
  //   - PAUSED: símbolo de pausa (dos barras), siempre vertical aunque el
  //     robot esté girado, y chasis gris pizarra. No parpadea: no es una alarma.
  //   - Resto: flecha que indica el sentido de marcha.
  import { ROBOT_COLORS } from '../lib/fleet.svelte.js';

  // loaded: lleva un palet encima (también si está en ERROR, en pausa o cargando batería
  // con el palet a bordo, a la espera de terminar la entrega).
  let { state = 'IDLE', angle = 0, loaded = null } = $props();

  let color = $derived(ROBOT_COLORS[state] ?? '#9aa8a1');
  let carrying = $derived(loaded ?? ['LOADING', 'TO_DROP', 'UNLOADING'].includes(state));
  let handling = $derived(state === 'LOADING' || state === 'UNLOADING');
</script>

<!-- sombra fuera del giro: la "luz" viene siempre del mismo sitio -->
<ellipse cx="1.5" cy="2.5" rx="15" ry="14" fill="#1c2a25" opacity="0.15" />

<g class="amr" class:error={state === 'ERROR'} style="transform: rotate({angle}deg)">
  <!-- ruedas motrices (laterales) -->
  <rect x="-6" y="-15" width="12" height="5" rx="2" fill="#2e3b36" />
  <rect x="-6" y="10" width="12" height="5" rx="2" fill="#2e3b36" />

  <!-- chasis -->
  <rect x="-14" y="-12" width="28" height="24" rx="6" fill={color}
        stroke="#1c2a25" stroke-opacity="0.35" stroke-width="1.5" />
  <!-- brillo -->
  <rect x="-11" y="-10" width="14" height="2.5" rx="1.25" fill="#fff" opacity="0.3" />
  <!-- parachoques trasero -->
  <path d="M -14 -6 Q -15.5 0 -14 6" stroke="#1c2a25" stroke-opacity="0.35"
        stroke-width="2.5" fill="none" stroke-linecap="round" />

  <!-- frontal: barra de sensores con LiDAR y pilotos -->
  <rect x="9" y="-9" width="4" height="18" rx="2" fill="#1c2a25" opacity="0.75" />
  <circle cx="11" cy="0" r="1.8" fill="#9fd3bd" />
  <rect x="12.6" y="-10" width="1.6" height="2.6" rx="0.6" fill="#fff6d5" />
  <rect x="12.6" y="7.4" width="1.6" height="2.6" rx="0.6" fill="#fff6d5" />

  <!-- lomo -->
  {#if carrying}
    <g class:handling>
      <rect x="-10" y="-8" width="16" height="16" rx="2" fill="#d6a46c" stroke="#8b5a2b" stroke-width="1.2" />
      <rect x="-10" y="-1.2" width="16" height="2.4" fill="#f1d3a8" />
    </g>
    {#if state === 'PAUSED'}
      <!-- pausado con el palet a bordo: distintivo de pausa sobre la caja -->
      <g class="pause" style="transform: translate(-2px, 0) rotate({-angle}deg)">
        <circle r="6.2" fill="#3f4a54" stroke="#fff" stroke-width="1.2" />
        <rect x="-3" y="-3.2" width="2.2" height="6.4" rx="0.7" fill="#fff" />
        <rect x="0.8" y="-3.2" width="2.2" height="6.4" rx="0.7" fill="#fff" />
      </g>
    {:else if state === 'ERROR'}
      <!-- avería con el palet a bordo: entrega en pausa -->
      <path d="M -2 -6 L 3 3 L -7 3 Z" fill="#d1495b" stroke="#fff" stroke-width="1.2" stroke-linejoin="round" />
      <path d="M -2 -3 L -2 0 M -2 1.6 L -2 1.7" stroke="#fff" stroke-width="1.3" stroke-linecap="round" />
    {:else if state === 'CHARGING' || state === 'TO_CHARGER'}
      <path class:pulse={state === 'CHARGING'} d="M -1 -6 L -5 0 L -2 0 L -3 5 L 2 -1 L -1 -1 Z"
            fill="#fde68a" stroke="#8a5a14" stroke-width="0.9" stroke-linejoin="round" />
    {/if}
  {:else}
    <rect x="-10" y="-8" width="16" height="16" rx="3" fill="#fff" opacity="0.25" />
    {#if state === 'CHARGING'}
      <path class="pulse" d="M -1 -6.5 L -6 1 L -2 1 L -3.5 6.5 L 2.5 -1.5 L -1.5 -1.5 Z"
            fill="#fde68a" stroke="#8a5a14" stroke-width="1" stroke-linejoin="round" />
    {:else if state === 'PAUSED'}
      <g class="pause" style="transform: translate(-2px, 0) rotate({-angle}deg)">
        <rect x="-5" y="-5.5" width="3.6" height="11" rx="1.2" fill="#fff" />
        <rect x="1.4" y="-5.5" width="3.6" height="11" rx="1.2" fill="#fff" />
      </g>
    {:else if state === 'ERROR'}
      <path d="M -2 -6 L 4 5 L -8 5 Z" fill="#fff" stroke="#fff" stroke-width="1.5" stroke-linejoin="round" />
      <path d="M -2 -2.5 L -2 1.5 M -2 3.3 L -2 3.4" stroke="#d1495b" stroke-width="1.6" stroke-linecap="round" />
    {:else}
      <path d="M -6 -4 L -1 0 L -6 4" fill="none" stroke="#fff" stroke-width="2"
            stroke-linecap="round" stroke-linejoin="round" opacity="0.85" />
    {/if}
  {/if}
</g>

<style>
  .amr { transition: transform 0.35s ease-out; }
  .error { animation: blink 0.8s steps(2) infinite; }
  .pulse { animation: pulse 1.2s ease-in-out infinite; transform-origin: center; transform-box: fill-box; }
  .handling { animation: bob 0.6s ease-in-out infinite alternate; }
  @keyframes blink { 50% { opacity: 0.45; } }
  @keyframes pulse { 50% { transform: scale(1.2); } }
  @keyframes bob { to { opacity: 0.75; } }
</style>
