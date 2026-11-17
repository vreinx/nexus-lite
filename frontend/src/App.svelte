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

  // Vista de planta: el mapa ocupa toda la pantalla y los paneles flotan
  // encima, a los lados. Al mapa se le dice cuánto ocupan (insets) para que
  // centre la planta en la zona libre y ningún panel tape nada.
  // En pantallas estrechas no hay sitio: los paneles van debajo del mapa.
  const EDGE = 16;               // separación de los paneles al borde (ver CSS)
  let innerWidth = $state(1280);
  let floating = $derived(innerWidth > 1100);
  let leftW = $state(0);
  let rightW = $state(0);
  let insets = $derived(floating ? { left: leftW + EDGE, right: rightW + EDGE } : {});

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

<svelte:window bind:innerWidth />

{#if checking}
  <p class="muted" style="padding: 24px">Cargando…</p>
{:else if !fleet.user}
  <LoginView onlogin={start} />
{:else}
<div class="shell" class:fill={view === 'planta' && floating}>
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
<main class="stage" class:floating>
  <div class="map-layer">
    {#if fleet.map}
      <MapView {insets} />
    {:else}
      <p class="muted loading">Cargando mapa… {mapError}</p>
    {/if}
  </div>

  <aside class="panel left" bind:offsetWidth={leftW}>
    <RobotList />
  </aside>

  <aside class="panel right" bind:offsetWidth={rightW}>
    <RobotDetail />
    <MissionPanel />
  </aside>
</main>
{/if}
</div>
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

  main { padding: 16px 20px; }

  /* Planta en pantalla estrecha: mapa arriba y paneles debajo */
  .stage { display: flex; flex-direction: column; gap: 16px; }
  .map-layer {
    position: relative;
    aspect-ratio: 3 / 2;
    border: 1px solid var(--border);
    border-radius: 10px;
    overflow: hidden;
  }
  .panel { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .loading { padding: 16px; }

  /* Planta a pantalla completa: mapa de fondo y paneles flotantes a los lados */
  .shell.fill { height: 100dvh; display: flex; flex-direction: column; overflow: hidden; }
  .stage.floating { flex: 1; min-height: 0; position: relative; display: block; padding: 0; }
  .stage.floating .map-layer { position: absolute; inset: 0; aspect-ratio: auto; border: none; border-radius: 0; }
  .stage.floating .panel {
    position: absolute;
    top: 16px;           /* = EDGE */
    bottom: 16px;        /* ocupan todo el costado */
    overflow-y: auto;
    scrollbar-width: thin;
  }
  .stage.floating .left { left: 16px; width: clamp(190px, 15vw, 250px); }
  .stage.floating .right { right: 16px; width: clamp(320px, 27vw, 400px); }
  /* Translúcidos: se adivina la cuadrícula del mapa por detrás */
  .stage.floating .panel :global(.card) {
    flex-shrink: 0;
    background: rgba(255, 255, 255, 0.45);
    border-color: rgba(157, 179, 168, 0.55);
    box-shadow: 0 6px 20px rgba(30, 59, 50, 0.13);
  }
  /* Izquierda: la flota llena el costado, con las tarjetas repartidas en altura */
  .stage.floating .left :global(.card) { flex: 1 0 auto; display: flex; flex-direction: column; }
  .stage.floating .left :global(.grid) { flex: 1; align-content: space-between; }
  .stage.floating .left :global(.robot) { background: rgba(255, 255, 255, 0.5); }
  /* Derecha: la lista de misiones crece hasta el final del costado */
  .stage.floating .right :global(.card:last-child) {
    flex: 1 0 200px; min-height: 0; display: flex; flex-direction: column;
  }
  .stage.floating .right :global(.card:last-child ul) { flex: 1 1 0; min-height: 0; max-height: none; }
</style>
