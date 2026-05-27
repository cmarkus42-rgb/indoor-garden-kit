<script lang="ts">
  import { get } from '$lib/api.js';
  import type { AlertsResponse, Alert } from '$lib/types.js';
  import { onMount } from 'svelte';

  let alerts = $state<Alert[]>([]);
  let tierFilter = $state('all');
  let sourceFilter = $state('');

  async function load() {
    const res = await get<AlertsResponse>('/api/alerts');
    alerts = res.alerts;
  }

  onMount(() => { load(); });

  const filtered = $derived(
    alerts.filter(a => {
      if (tierFilter !== 'all' && a.tier !== tierFilter) return false;
      if (sourceFilter && !a.source.toLowerCase().includes(sourceFilter.toLowerCase())) return false;
      return true;
    })
  );
</script>

<h1>Event Log</h1>

<div style="margin-bottom: 0.5rem; display: flex; gap: 1rem; align-items: center;">
  <label>
    Tier:
    <select bind:value={tierFilter}>
      <option value="all">All</option>
      <option value="info">Info</option>
      <option value="warning">Warning</option>
      <option value="critical">Critical</option>
    </select>
  </label>
  <label>
    Source:
    <input type="text" bind:value={sourceFilter} placeholder="Filter source..." />
  </label>
  <span class="muted">{filtered.length} / {alerts.length}</span>
</div>

{#if filtered.length === 0}
  <p class="muted">No alerts</p>
{:else}
  <table>
    <thead>
      <tr><th>Timestamp</th><th>Tier</th><th>Source</th><th>Message</th><th>Resolved</th></tr>
    </thead>
    <tbody>
      {#each filtered as a}
        <tr>
          <td>{a.timestamp}</td>
          <td>{a.tier}</td>
          <td>{a.source}</td>
          <td>{a.message}</td>
          <td>{a.resolved_at ?? '\u2014'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
