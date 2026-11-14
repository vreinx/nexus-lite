<script>
  import { onMount } from 'svelte';
  import { fleet, connect, loadMap } from './lib/fleet.svelte.js';
  import ConnectionBadge from './components/ConnectionBadge.svelte';
  import MapView from './components/MapView.svelte';
  import RobotList from './components/RobotList.svelte';
  import RobotDetail from './components/RobotDetail.svelte';
  import MissionPanel from './components/MissionPanel.svelte';

  let mapError = $state('');

  async function loadMapWithRetry() {
    try {
      await loadMap();
      mapError = '';
    } catch (e) {
      mapError = e.message;
      setTimeout(loadMapWithRetry, 2000);
    }
  }

  onMount(() => {
    loadMapWithRetry();
    connect();
  });
</script>

<header>
  <div class="brand">
    <strong>NEXUS Lite</strong>
    <span class="muted">Gestor de flota AMR</span>
  </div>
  <ConnectionBadge />
</header>

<main>
  <section class="left">
    <div class="card map-card">
      <h2>Planta</h2>
      {#if fleet.map}
        <MapView />
      {:else}
        <p class="muted">Cargando mapa… {mapError}</p>
      {/if}
    </div>
    <RobotList />
  </section>

  <aside class="right">
    <RobotDetail />
    <MissionPanel />
  </aside>
</main>

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: #0f172a;
    color: #fff;
  }
  .brand { display: flex; gap: 12px; align-items: baseline; }
  .brand strong { font-size: 18px; }
  .brand .muted { color: #94a3b8; }

  main {
    display: grid;
    grid-template-columns: minmax(0, 1fr) 400px;
    gap: 16px;
    padding: 16px 20px;
    align-items: start;
  }
  .left, .right { display: flex; flex-direction: column; gap: 16px; min-width: 0; }

  @media (max-width: 1100px) {
    main { grid-template-columns: 1fr; }
  }
</style>
