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
  .online .dot { background: #8fd1b0; box-shadow: 0 0 0 3px rgba(143, 209, 176, 0.3); }
  .connecting .dot { background: #e0a458; animation: blink 1s infinite; }
  .offline { background: rgba(209, 73, 91, 0.3); }
  .offline .dot { background: #f08a97; }
  .retry { color: #f6c1c8; }
  button { padding: 2px 10px; font-size: 12px; }
  @keyframes blink { 50% { opacity: 0.3; } }
</style>
