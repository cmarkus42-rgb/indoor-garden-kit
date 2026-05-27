<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { SchedulesResponse, LightSchedule } from '$lib/types.js';
  import { onMount } from 'svelte';

  let schedules = $state<LightSchedule[]>([]);

  async function load() {
    const res = await get<SchedulesResponse>('/api/schedules');
    schedules = res.schedules;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'schedule_pushed') {
      load();
    }
  });
</script>

<h1>Light Schedules</h1>

{#if schedules.length === 0}
  <p class="muted">No schedules</p>
{:else}
  <table>
    <thead>
      <tr><th>Device</th><th>Date</th><th>On</th><th>Off</th><th>Pushed</th></tr>
    </thead>
    <tbody>
      {#each schedules as s}
        <tr>
          <td>{s.device_id}</td>
          <td>{s.date}</td>
          <td>{s.on_time}</td>
          <td>{s.off_time}</td>
          <td>{s.pushed_at ?? '\u2014'}</td>
        </tr>
      {/each}
    </tbody>
  </table>

  <h2>Recipe Snapshots</h2>
  {#each schedules as s}
    {#if s.recipe_snapshot && Object.keys(s.recipe_snapshot).length > 0}
      <h3>{s.device_id} &mdash; {s.date}</h3>
      <pre>{JSON.stringify(s.recipe_snapshot, null, 2)}</pre>
    {/if}
  {/each}
{/if}
