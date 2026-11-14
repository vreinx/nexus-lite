<script>
  // F-04: estado del canal en tiempo real, visible siempre en la cabecera.
  import { fleet, reconnectNow } from '../lib/fleet.svelte.js';

  const LABELS = {
    online: 'En vivo',
    connecting: 'Conectando…',
    offline: 'Sin conexión',
  };
</script>

<div class="conn {fleet.connection}" role="status" aria-live="polite">
  <span class="dot"></span>
  <span>{LABELS[fleet.connection]}</span>
  {#if fleet.connection === 'offline'}
    <span class="retry">· reintento en {fleet.retryIn} s</span>
    <button onclick={reconnectNow}>Reintentar ya</button>
  {/if}
</div>

<style>
  .conn {
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    padding: 4px 12px;
    border-radius: 999px;
    background: rgba(255, 255, 255, 0.08);
  }
  .dot { width: 10px; height: 10px; border-radius: 50%; }
  .online .dot { background: #22c55e; box-shadow: 0 0 0 3px rgba(34, 197, 94, 0.3); }
  .connecting .dot { background: #f59e0b; animation: blink 1s infinite; }
  .offline { background: rgba(220, 38, 38, 0.25); }
  .offline .dot { background: #ef4444; }
  .retry { color: #fca5a5; }
  button { padding: 2px 10px; font-size: 12px; }
  @keyframes blink { 50% { opacity: 0.3; } }
</style>
