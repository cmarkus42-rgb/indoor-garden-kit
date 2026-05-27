<script lang="ts">
  import { clearAuth } from '$lib/auth.js';
  import { get } from '$lib/api.js';
  import type { StatusResponse, PollingResponse, Device } from '$lib/types.js';
  import { onMount } from 'svelte';

  let devices = $state<Device[]>([]);
  let polling = $state<Record<string, unknown>>({});

  async function loadData() {
    try {
      const status = await get<StatusResponse>('/api/status');
      devices = status.devices;
    } catch { /* ignore */ }
    try {
      const poll = await get<PollingResponse>('/api/polling');
      polling = poll.loops;
    } catch { /* ignore */ }
  }

  onMount(() => { loadData(); });
</script>

<h1>Einstellungen</h1>

<div class="panel" style="padding: var(--s-4); margin-bottom: var(--s-4);">
  <div class="section-h">Authentifizierung</div>
  <div style="padding: var(--s-4);">
    <p>Angemeldet. <button class="btn ghost" onclick={() => clearAuth()}>Abmelden</button></p>
  </div>
</div>

<div class="panel" style="padding: var(--s-4); margin-bottom: var(--s-4);">
  <div class="section-h">Polling Status</div>
  <pre>{JSON.stringify(polling, null, 2)}</pre>
</div>

<div class="panel" style="padding: var(--s-4);">
  <div class="section-h">Geraete</div>
  {#if devices.length === 0}
    <p class="muted" style="padding: var(--s-4);">Keine Geraete</p>
  {:else}
    <table>
      <thead><tr><th>Name</th><th>Typ</th><th>Zone</th><th>Status</th><th>Zuletzt</th></tr></thead>
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
</div>
