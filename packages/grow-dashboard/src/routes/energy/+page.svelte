<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';

  let plugs = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());

  async function load() {
    const status = await get<StatusResponse>('/api/status');
    plugs = status.devices.filter(d => d.device_type === 'shelly_plug');
    const map = new Map<string, SensorReading[]>();
    for (const d of plugs) {
      const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=20`);
      map.set(d.id, res.readings);
    }
    readings = map;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update' && evt.data.source === 'shelly') {
      load();
    }
  });

  function latestValue(deviceReadings: SensorReading[], metric: string): string {
    const r = deviceReadings.find(r => r.metric === metric);
    return r ? String(r.value) : '\u2014';
  }
</script>

<h1>Energy</h1>

{#if plugs.length === 0}
  <p class="muted">No plugs</p>
{:else}
  <table>
    <thead>
      <tr><th>Plug</th><th>Zone</th><th>Power (W)</th><th>Energy (kWh)</th><th>Temp (C)</th></tr>
    </thead>
    <tbody>
      {#each plugs as plug}
        {@const devReadings = readings.get(plug.id) ?? []}
        <tr>
          <td>{plug.name}</td>
          <td>{plug.zone}</td>
          <td>{latestValue(devReadings, 'power')}</td>
          <td>{latestValue(devReadings, 'energy')}</td>
          <td>{latestValue(devReadings, 'temperature')}</td>
        </tr>
      {/each}
    </tbody>
  </table>

  {#each plugs as plug}
    {@const devReadings = readings.get(plug.id) ?? []}
    {#if devReadings.length > 0}
      <h2>{plug.name} &mdash; History</h2>
      <table>
        <thead><tr><th>Timestamp</th><th>Metric</th><th>Value</th></tr></thead>
        <tbody>
          {#each devReadings as r}
            <tr>
              <td>{r.timestamp}</td>
              <td>{r.metric}</td>
              <td>{r.value}</td>
            </tr>
          {/each}
        </tbody>
      </table>
    {/if}
  {/each}
{/if}
