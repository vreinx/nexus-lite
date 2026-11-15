<script>
  // Marca propia de NEXUS Lite: un nodo central conectado a varios nodos
  // (nexus = conexión), en el verde corporativo. No es un logo de AND&OR.
  let { size = 34 } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 48 48" aria-hidden="true">
  <rect width="48" height="48" rx="11" fill="#6ca087" />
  <g stroke="#fff" stroke-width="3" stroke-linecap="round">
    <line x1="24" y1="24" x2="12" y2="13" />
    <line x1="24" y1="24" x2="37" y2="15" />
    <line x1="24" y1="24" x2="15" y2="36" />
    <line x1="24" y1="24" x2="35" y2="35" opacity="0.55" />
  </g>
  <circle cx="12" cy="13" r="4" fill="#fff" />
  <circle cx="37" cy="15" r="4" fill="#fff" />
  <circle cx="15" cy="36" r="4" fill="#fff" />
  <circle cx="35" cy="35" r="3.2" fill="#fff" opacity="0.55" />
  <circle cx="24" cy="24" r="6.5" fill="#1e3b32" stroke="#fff" stroke-width="3" />
</svg>
