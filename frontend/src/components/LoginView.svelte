<script>
  // Pantalla de inicio de sesión. Dos usuarios del ejercicio, cada uno con su rol.
  import { fleet, login } from '../lib/fleet.svelte.js';
  import Logo from './Logo.svelte';

  let { onlogin } = $props();

  let username = $state('');
  let password = $state('');
  let error = $state('');
  let sending = $state(false);

  async function submit(e) {
    e.preventDefault();
    error = '';
    sending = true;
    try {
      await login(username.trim(), password);
      onlogin?.();
    } catch (err) {
      error = err.message;
    } finally {
      sending = false;
    }
  }

  const fill = (u) => {
    username = u;
    password = u;
  };
</script>

<div class="screen">
  <form class="card login" onsubmit={submit}>
    <div class="brand">
      <Logo size={44} />
      <div>
        <div class="name"><strong>NEXUS</strong><span class="lite">Lite</span></div>
        <div class="sub">Gestor de flota AMR</div>
      </div>
    </div>

    <h1>Iniciar sesión</h1>
    {#if fleet.authMessage}<p class="notice" role="status">{fleet.authMessage}</p>{/if}

    <label>Usuario
      <input autocomplete="username" bind:value={username} required />
    </label>
    <label>Contraseña
      <input type="password" autocomplete="current-password" bind:value={password} required />
    </label>
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <button class="primary" type="submit" disabled={sending}>Entrar</button>

    <div class="roles">
      <div class="roles-title">Usuarios del ejercicio</div>
      <button type="button" class="role" onclick={() => fill('operador')}>
        <span class="badge op">Operador</span>
        <span><span class="mono">operador / operador</span><br />Ve la planta y actúa: crea y cancela órdenes, palets y robots</span>
      </button>
      <button type="button" class="role" onclick={() => fill('consulta')}>
        <span class="badge ro">Consulta</span>
        <span><span class="mono">consulta / consulta</span><br />Solo puede ver la planta, las órdenes y el historial</span>
      </button>
    </div>
  </form>
</div>

<style>
  .screen {
    min-height: 100vh;
    display: grid;
    place-items: center;
    background: linear-gradient(160deg, var(--brand-deep) 0%, #2b5245 100%);
    padding: 24px;
  }
  .login { width: min(400px, 100%); display: flex; flex-direction: column; gap: 12px; padding: 28px; }
  .brand { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
  .name { font-size: 20px; letter-spacing: 0.06em; }
  .name strong { font-weight: 800; }
  .lite { font-weight: 300; margin-left: 5px; color: var(--brand); }
  .sub { font-size: 12px; color: var(--muted); }
  h1 { font-size: 18px; margin: 8px 0 0; }
  label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
  input { font-size: 14px; padding: 8px 10px; }
  button.primary { padding: 9px; font-size: 14px; }
  .error { color: var(--danger); font-size: 13px; margin: 0; }
  .notice { color: #9a6418; background: #fbefd9; padding: 6px 10px; border-radius: 6px; font-size: 13px; margin: 0; }
  .roles { border-top: 1px solid var(--border); padding-top: 12px; display: flex; flex-direction: column; gap: 8px; }
  .roles-title { font-size: 11px; text-transform: uppercase; letter-spacing: 0.05em; color: var(--muted); }
  .role { display: flex; gap: 10px; align-items: flex-start; text-align: left; font-size: 12px;
          color: var(--muted); background: var(--bg); border-color: transparent; }
  .role:hover { border-color: var(--brand); }
  .role .mono { color: var(--text); }
  .op { background: var(--brand-dark); }
  .ro { background: #4a90a4; }
</style>
