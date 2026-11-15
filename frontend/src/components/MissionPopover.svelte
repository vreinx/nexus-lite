<script>
  // Crear una orden desde el mapa: se abre al hacer clic en una estación de recogida.
  import { fleet, createMission, declarePallet } from '../lib/fleet.svelte.js';

  let { station, style = '', onclose } = $props();

  let drops = $derived(fleet.map.stations.filter((s) => s.type === 'DROP'));
  let load = $derived(fleet.stations[station.id]);
  let hasPallet = $derived(!!load?.pallet);
  let reservedBy = $derived(load?.reserved_by);
  let destination = $state(null);
  let priority = $state(2);
  let error = $state('');
  let sending = $state(false);

  $effect(() => {
    if (!destination && drops.length) destination = drops[0].id;
  });

  async function declare() {
    error = '';
    try {
      await declarePallet(station.id);
    } catch (e) {
      error = e.message;
    }
  }

  async function create() {
    error = '';
    sending = true;
    try {
      await createMission(station.id, destination, priority);
      onclose();
    } catch (e) {
      error = e.message;
    } finally {
      sending = false;
    }
  }
</script>

<svelte:window onkeydown={(e) => e.key === 'Escape' && onclose()} />

<div class="pop" {style} role="dialog" aria-label="Nueva orden desde {station.id}">
  <div class="head">
    <strong>Nueva orden desde {station.id}</strong>
    <button class="x" onclick={onclose} aria-label="Cerrar">×</button>
  </div>

  {#if !hasPallet}
    <p class="info">No hay palet en {station.id}. Declara uno para poder crear una orden.</p>
    {#if error}<p class="error">{error}</p>{/if}
    <div class="actions">
      <button onclick={onclose}>Cerrar</button>
      <button class="primary" onclick={declare}>Declarar palet</button>
    </div>
  {:else if reservedBy}
    <p class="info">El palet de {station.id} ya tiene una orden asignada
      (<span class="mono">{reservedBy.slice(0, 8)}</span>).</p>
    <div class="actions"><button onclick={onclose}>Cerrar</button></div>
  {:else}
  <div class="label">Destino</div>
  <div class="chips">
    {#each drops as d}
      {@const busy = fleet.stations[d.id]?.pallet}
      <button class:on={destination === d.id} onclick={() => (destination = d.id)}
              title={busy ? 'Ocupado: aún tiene el palet de una entrega' : ''}>
        {d.id}{#if busy}<span class="busy"> · ocupado</span>{/if}
      </button>
    {/each}
  </div>

  <div class="label">Prioridad</div>
  <div class="chips">
    {#each [[1, 'Alta'], [2, 'Media'], [3, 'Baja']] as [p, txt]}
      <button class="p{p}" class:on={priority === p} onclick={() => (priority = p)}>{p} · {txt}</button>
    {/each}
  </div>

  {#if error}<p class="error">{error}</p>{/if}

  <div class="actions">
    <button onclick={onclose}>Cancelar</button>
    <button class="primary" onclick={create} disabled={sending || !destination}>
      Crear {station.id} → {destination}
    </button>
  </div>
  {/if}
</div>

<style>
  .pop {
    position: absolute;
    z-index: 5;
    width: 290px;
    background: #fff;
    border: 1px solid var(--border);
    border-radius: 10px;
    box-shadow: 0 10px 30px rgba(30, 59, 50, 0.18);
    padding: 12px 14px;
  }
  .head { display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
  .x { border: none; background: none; font-size: 20px; line-height: 1; padding: 0 4px; color: var(--muted); }
  .label { font-size: 12px; color: var(--muted); margin: 8px 0 4px; }
  .chips { display: flex; gap: 6px; flex-wrap: wrap; }
  .chips button { padding: 4px 10px; font-size: 13px; }
  .chips button.on { background: var(--brand-dark); color: #fff; border-color: var(--brand-dark); }
  .chips .p1.on { background: #a3313e; border-color: #a3313e; }
  .chips .p2.on { background: #9a6418; border-color: #9a6418; }
  .chips .p3.on { background: #2f6e80; border-color: #2f6e80; }
  .actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px; }
  .error { color: var(--danger); font-size: 12px; margin: 8px 0 0; }
  .info { font-size: 13px; color: var(--muted); margin: 6px 0 4px; }
  .busy { font-size: 11px; color: #9a6418; }
</style>
