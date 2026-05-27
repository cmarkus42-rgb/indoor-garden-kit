<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, Device } from '$lib/types.js';
  import { onMount } from 'svelte';

  let devices = $state<Device[]>([]);

  async function load() {
    const res = await get<StatusResponse>('/api/status');
    devices = res.devices;
  }

  onMount(() => { load(); });

  // Refresh on device_status SSE events
  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'device_status') {
      load();
    }
  });
</script>

<h1>Device Overview</h1>

{#if devices.length === 0}
  <p class="muted">No devices</p>
{:else}
  <table>
    <thead>
      <tr><th>Name</th><th>Type</th><th>Zone</th><th>Status</th><th>Last Seen</th></tr>
    </thead>
    <tbody>
      {#each devices as d}
        <tr>
          <td>{d.name}</td>
          <td>{d.device_type}</td>
          <td>{d.zone}</td>
          <td>{d.status}</td>
          <td>{d.last_seen}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
