<script lang="ts">
  import { get } from '$lib/api.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { toTimeseries, type TimeseriesPoint } from '$lib/types.js';
  import { onMount } from 'svelte';

  // ── Device + Metric Selection ──

  let devices = $state<Device[]>([]);
  let selectedDevices = $state<Set<string>>(new Set());
  let allPoints = $state<TimeseriesPoint[]>([]);
  let loading = $state(false);

  // Source mapping for toTimeseries
  const sourceMap: Record<string, string> = {
    shelly_plug: 'shelly',
    shelly_relay: 'shelly',
    blu_ht: 'blu_ht',
    ecowitt_soil: 'ecowitt',
    ecowitt_indoor: 'ecowitt'
  };

  async function loadDevices() {
    const res = await get<StatusResponse>('/api/status');
    devices = res.devices;
  }

  async function loadSelected() {
    if (selectedDevices.size === 0) {
      allPoints = [];
      return;
    }
    loading = true;
    const points: TimeseriesPoint[] = [];
    for (const id of selectedDevices) {
      const device = devices.find(d => d.id === id);
      if (!device) continue;
      const res = await get<ReadingsResponse>(`/api/readings/${id}?limit=100`);
      const source = sourceMap[device.device_type] ?? 'unknown';
      for (const r of res.readings) {
        points.push(toTimeseries(r, source));
      }
    }
    // Sort by timestamp descending
    points.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
    allPoints = points;
    loading = false;
  }

  onMount(() => { loadDevices(); });

  function toggleDevice(id: string) {
    const next = new Set(selectedDevices);
    if (next.has(id)) {
      next.delete(id);
    } else {
      next.add(id);
    }
    selectedDevices = next;
    loadSelected();
  }

  // ── Metric Filtering ──

  let metricFilter = $state('all');

  const availableMetrics = $derived(
    [...new Set(allPoints.map(p => p.metric))].sort()
  );

  const filtered = $derived(
    metricFilter === 'all'
      ? allPoints
      : allPoints.filter(p => p.metric === metricFilter)
  );

  // ── Correlation View: pivot by timestamp ──
  // Group readings by rounded timestamp (nearest 30s) to align cross-device readings

  const correlationRows = $derived(() => {
    if (selectedDevices.size < 2) return { columns: [] as string[], rows: [] as { timestamp: string; values: (number | null)[] }[] };

    const buckets = new Map<string, Map<string, number>>();
    for (const p of allPoints) {
      // Round to nearest 30s for alignment
      const ts = new Date(p.timestamp);
      ts.setSeconds(Math.round(ts.getSeconds() / 30) * 30, 0);
      const key = ts.toISOString();
      if (!buckets.has(key)) buckets.set(key, new Map());
      const label = `${p.device_id}:${p.metric}`;
      buckets.get(key)!.set(label, p.value);
    }

    // Get all column keys
    const columns = [...new Set(allPoints.map(p => `${p.device_id}:${p.metric}`))].sort();

    // Convert to rows
    const rows = [...buckets.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .slice(0, 50)
      .map(([ts, vals]) => ({
        timestamp: ts,
        values: columns.map(col => vals.get(col) ?? null)
      }));

    return { columns, rows } as { columns: string[]; rows: { timestamp: string; values: (number | null)[] }[] };
  });
</script>

<h1>Investigation View</h1>
<p class="muted">Select devices to load their readings onto a shared timeline. Select 2+ devices to see the correlation table.</p>

<h2>Devices</h2>
<div style="display: flex; flex-wrap: wrap; gap: 0.25rem; margin-bottom: 1rem;">
  {#each devices as d}
    <button
      onclick={() => toggleDevice(d.id)}
      style="background: {selectedDevices.has(d.id) ? '#333' : '#eee'}; color: {selectedDevices.has(d.id) ? '#fff' : '#333'}; border: 1px solid #999; border-radius: 3px; padding: 2px 8px; font-size: 12px;"
    >
      {d.name}
    </button>
  {/each}
</div>

{#if loading}
  <p class="muted">Loading readings...</p>
{:else if allPoints.length === 0}
  <p class="muted">No devices selected</p>
{:else}
  <div style="display: flex; gap: 1rem; align-items: center; margin-bottom: 0.5rem;">
    <label>
      Metric:
      <select bind:value={metricFilter}>
        <option value="all">All ({allPoints.length})</option>
        {#each availableMetrics as m}
          <option value={m}>{m} ({allPoints.filter(p => p.metric === m).length})</option>
        {/each}
      </select>
    </label>
    <span class="muted">{filtered.length} points across {selectedDevices.size} devices</span>
  </div>

  <!-- Flat timeline view -->
  <h2>Timeline</h2>
  <table>
    <thead>
      <tr><th>Timestamp</th><th>Device</th><th>Metric</th><th>Value</th><th>Source</th></tr>
    </thead>
    <tbody>
      {#each filtered.slice(0, 100) as p}
        <tr>
          <td>{p.timestamp}</td>
          <td>{p.device_id}</td>
          <td>{p.metric}</td>
          <td>{p.value}</td>
          <td>{p.source}</td>
        </tr>
      {/each}
    </tbody>
  </table>
  {#if filtered.length > 100}
    <p class="muted">Showing 100 of {filtered.length} — full view with charts in design session</p>
  {/if}

  <!-- Correlation table (2+ devices) -->
  {#if selectedDevices.size >= 2}
    {@const corr = correlationRows()}
    {#if corr.rows.length > 0}
      <h2>Correlation (time-aligned)</h2>
      <p class="muted">Readings bucketed to 30s intervals. Gaps shown as —.</p>
      <div style="overflow-x: auto;">
        <table>
          <thead>
            <tr>
              <th>Timestamp</th>
              {#each corr.columns as col}
                <th style="font-size: 11px; white-space: nowrap;">{col}</th>
              {/each}
            </tr>
          </thead>
          <tbody>
            {#each corr.rows as row}
              <tr>
                <td style="white-space: nowrap;">{row.timestamp}</td>
                {#each row.values as v}
                  <td>{v !== null ? v : '\u2014'}</td>
                {/each}
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  {/if}
{/if}
