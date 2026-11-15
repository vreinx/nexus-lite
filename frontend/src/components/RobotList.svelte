<script>
  import { fleet, ROBOT_COLORS, batteryColor } from '../lib/fleet.svelte.js';

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
        <div class="bar"><div style="width:{r.battery}%;background:{batteryColor(r.battery)}"></div></div>
        <div class="muted small">{r.battery}% · ({r.x}, {r.y})</div>
      </button>
    {/each}
  </div>
</div>

<style>
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px; }
  .robot { text-align: left; padding: 10px; display: flex; flex-direction: column; gap: 6px; }
  .robot.selected { border-color: var(--accent); box-shadow: 0 0 0 2px rgba(62, 117, 96, 0.2); }
  .top { display: flex; justify-content: space-between; align-items: center; }
  .bar { height: 6px; background: #e3eae6; border-radius: 3px; overflow: hidden; }
  .bar div { height: 100%; transition: width 1s linear; }
  .small { font-size: 12px; }
</style>
