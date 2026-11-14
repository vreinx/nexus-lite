<script>
  import { fleet, ROBOT_COLORS } from '../lib/fleet.svelte.js';

  let robots = $derived(Object.values(fleet.robots).sort((a, b) => a.id.localeCompare(b.id)));
</script>

<div class="card">
  <h2>Flota</h2>
  <div class="grid">
    {#each robots as r (r.id)}
      <button class="robot" class:selected={fleet.selectedRobot === r.id}
              onclick={() => (fleet.selectedRobot = r.id)}>
        <div class="top">
          <strong>{r.id}</strong>
          <span class="badge" style="background:{ROBOT_COLORS[r.state]}">{r.state}</span>
        </div>
        <div class="bar"><div style="width:{r.battery}%;background:{r.battery < 20 ? '#ef4444' : r.battery < 30 ? '#f59e0b' : '#22c55e'}"></div></div>
        <div class="muted small">{r.battery}% · ({r.x}, {r.y})</div>
      </button>
    {/each}
  </div>
</div>

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .robot { text-align: left; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
  .robot.selected { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(15, 76, 129, 0.2); }
  .top { display: flex; justify-content: space-between; align-items: center; }
  .bar { height: 6px; background: #e2e8f0; border-radius: 3px; overflow: hidden; }
  .bar div { height: 100%; transition: width 1s linear; }
  .small { font-size: 12px; }
</style>
