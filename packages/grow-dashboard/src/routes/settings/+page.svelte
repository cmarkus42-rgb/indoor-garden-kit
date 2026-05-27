<script lang="ts">
  import { verified, verifyPin, clearAuth } from '$lib/auth.js';
  import { get } from '$lib/api.js';
  import type { StatusResponse, PollingResponse, Device } from '$lib/types.js';
  import { onMount } from 'svelte';

  let pin = $state('');
  let pinError = $state('');
  let devices = $state<Device[]>([]);
  let polling = $state<Record<string, unknown>>({});

  async function handleVerify() {
    pinError = '';
    const ok = await verifyPin(pin);
    if (!ok) {
      pinError = 'Invalid PIN';
    }
    pin = '';
  }

  async function loadData() {
    try {
      const status = await get<StatusResponse>('/api/status');
      devices = status.devices;
    } catch { /* ignore when not authed yet */ }
    try {
      const poll = await get<PollingResponse>('/api/polling');
      polling = poll.loops;
    } catch { /* ignore */ }
  }

  onMount(() => { loadData(); });
</script>

<h1>Settings</h1>

<h2>Authentication</h2>
{#if $verified}
  <p>Authenticated. <button onclick={() => clearAuth()}>Clear</button></p>
{:else}
  <form onsubmit={(e) => { e.preventDefault(); handleVerify(); }}>
    <input type="password" bind:value={pin} placeholder="PIN" />
    <button type="submit">Verify</button>
  </form>
  {#if pinError}<p class="error">{pinError}</p>{/if}
{/if}

<h2>Polling Status</h2>
<pre>{JSON.stringify(polling, null, 2)}</pre>

<h2>Devices</h2>
{#if devices.length === 0}
  <p class="muted">No devices</p>
{:else}
  <table>
    <thead><tr><th>Name</th><th>Type</th><th>Zone</th><th>Status</th><th>Last Seen</th></tr></thead>
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
