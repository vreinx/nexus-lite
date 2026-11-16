<script>
  import { onMount } from 'svelte';
  import { fleet, connect, loadMap, logout, restoreSession } from './lib/fleet.svelte.js';
  import LoginView from './components/LoginView.svelte';
  import ConnectionBadge from './components/ConnectionBadge.svelte';
  import Logo from './components/Logo.svelte';
  import MapView from './components/MapView.svelte';
  import RobotList from './components/RobotList.svelte';
  import RobotDetail from './components/RobotDetail.svelte';
  import MissionPanel from './components/MissionPanel.svelte';
  import HistoryView from './components/HistoryView.svelte';

  // Navegación mínima por hash: #/ (planta) y #/historial
  const VIEWS = { '': 'planta', historial: 'historial' };
  const viewFromHash = () => VIEWS[location.hash.replace(/^#\/?/, '').split('?')[0]] ?? 'planta';
  let view = $state(viewFromHash());

  let mapError = $state('');

  let checking = $state(true);   // comprobando si hay una sesión guardada

  async function loadMapWithRetry() {
    if (!fleet.user) return;
    try {
      await loadMap();
      mapError = '';
    } catch (e) {
      mapError = e.message;
      setTimeout(loadMapWithRetry, 2000);
    }
  }

  // Tras iniciar sesión (o recuperar la guardada): mapa y tiempo real
  function start() {
    loadMapWithRetry();
    connect();
  }

  onMount(() => {
    restoreSession().then((user) => {
      checking = false;
      if (user) start();
    });
    const onHash = () => (view = viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  });
</script>

{#if checking}
  <p class="muted" style="padding: 24px">Cargando…</p>
{:else if !fleet.user}
  <LoginView onlogin={start} />
{:else}
<header>
  <div class="brand">
    <Logo />
    <div class="titles">
      <div class="name"><strong>NEXUS</strong><span class="lite">Lite</span></div>
      <div class="sub">Gestor de flota AMR · Prueba técnica para AND&amp;OR</div>
    </div>
  </div>
  <nav>
    <a href="#/" class:active={view === 'planta'}>Planta</a>
    <a href="#/historial" class:active={view === 'historial'}>Historial</a>
  </nav>
  <ConnectionBadge />
  <div class="user" title="Sesión iniciada como {fleet.user.username}">
    <span class="role {fleet.user.role === 'OPERATOR' ? 'op' : 'ro'}">
      {fleet.user.role === 'OPERATOR' ? 'Operador' : 'Consulta · solo lectura'}
    </span>
    <span class="who">{fleet.user.username}</span>
    <button class="logout" onclick={() => logout()}>Salir</button>
  </div>
</header>

{#if view === 'historial'}
  <main class="single">
    {#if fleet.map}<HistoryView />{:else}<p class="muted">Cargando…</p>{/if}
  </main>
{:else}
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
{/if}
{/if}

<style>
  header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 20px;
    background: var(--brand-deep);
    color: #fff;
    border-bottom: 3px solid var(--brand);
  }
  .brand { display: flex; gap: 12px; align-items: center; }
  header { gap: 20px; }
  nav { display: flex; gap: 4px; margin-right: auto; margin-left: 24px; }
  nav a { color: #cfe3d9; text-decoration: none; padding: 6px 14px; border-radius: 6px; font-weight: 500; }
  nav a:hover { background: rgba(255, 255, 255, 0.08); }
  nav a.active { background: var(--brand); color: #fff; }
  main.single { display: block; }
  .user { display: flex; align-items: center; gap: 8px; margin-left: 12px; font-size: 13px; }
  .role { font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; color: #fff; }
  .role.op { background: var(--brand); }
  .role.ro { background: #4a90a4; }
  .who { color: #cfe3d9; }
  .logout { padding: 3px 10px; font-size: 12px; background: transparent; color: #cfe3d9;
            border-color: rgba(255, 255, 255, 0.25); }
  .logout:hover { background: rgba(255, 255, 255, 0.1); }
  .name { font-size: 19px; letter-spacing: 0.06em; line-height: 1.1; }
  .name strong { font-weight: 800; }
  .lite { font-weight: 300; margin-left: 5px; color: #a9d1bd; }
  .sub { font-size: 12px; color: #a9c2b6; }

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
