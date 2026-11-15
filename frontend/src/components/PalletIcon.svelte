<script>
  // Palet visto desde arriba: tarima de madera con una carga embalada encima.
  // Centrado en (0,0). Si `timer` > 0 (palet entregado en un destino), se
  // dibuja un anillo que se vacía en `timer` segundos hasta que se retira.
  let { timer = 0, reserved = false } = $props();

  const R = 17;
  const CIRC = 2 * Math.PI * R;
</script>

<g class="pallet">
  {#if timer > 0}
    <circle r={R} fill="none" stroke="#e3eae6" stroke-width="2.5" />
    <circle r={R} fill="none" stroke="#d4903f" stroke-width="2.5" stroke-linecap="round"
            stroke-dasharray={CIRC} class="countdown"
            style="--circ:{CIRC}; animation-duration:{timer}s" transform="rotate(-90)" />
  {/if}

  <!-- tarima: tablas -->
  <rect x="-11" y="-9" width="22" height="18" rx="1.5" fill="#b07a45" />
  {#each [-7.5, -2.5, 2.5, 7.5] as x}
    <rect x={x - 1.8} y="-9" width="3.6" height="18" rx="0.8" fill="#c9935a" />
  {/each}
  <rect x="-11" y="-9" width="22" height="18" rx="1.5" fill="none" stroke="#7a4f26" stroke-width="1" />

  <!-- carga embalada -->
  <rect x="-8" y="-6.5" width="16" height="13" rx="1.5" fill="#e8c491" stroke="#8b5a2b" stroke-width="1" />
  <rect x="-8" y="-1" width="16" height="2" fill="#f5dfbd" />
  <rect x="-1" y="-6.5" width="2" height="13" fill="#f5dfbd" opacity="0.8" />

  {#if reserved}
    <!-- palet ya asignado a una orden -->
    <circle cx="9" cy="-8" r="4.2" fill="#4a90a4" stroke="#fff" stroke-width="1.2" />
    <path d="M 7.2 -8 L 8.6 -6.6 L 10.9 -9.4" fill="none" stroke="#fff" stroke-width="1.3"
          stroke-linecap="round" stroke-linejoin="round" />
  {/if}
</g>

<style>
  .pallet { pointer-events: none; }
  .countdown { animation-name: drain; animation-timing-function: linear; animation-fill-mode: forwards; }
  @keyframes drain { from { stroke-dashoffset: 0; } to { stroke-dashoffset: var(--circ); } }
</style>
