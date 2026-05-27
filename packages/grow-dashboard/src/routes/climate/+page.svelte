<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';

  let climateDevices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());

  async function load() {
    const status = await get<StatusResponse>('/api/status');
    climateDevices = status.devices.filter(d =>
      d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor'
    );
    const map = new Map<string, SensorReading[]>();
    for (const d of climateDevices) {
      const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=20`);
      map.set(d.id, res.readings);
    }
    readings = map;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update') {
      const source = evt.data.source as string;
      if (source === 'blu_ht' || source === 'ecowitt') {
        load();
      }
    }
  });

  function latestByMetric(deviceReadings: SensorReading[], metric: string): number | null {
    const r = deviceReadings.find(r => r.metric === metric);
    return r ? r.value : null;
  }

  function fmt(v: number | null, digits = 1): string {
    return v !== null ? v.toFixed(digits) : '\u2014';
  }
</script>

<h1>Climate</h1>

{#if climateDevices.length === 0}
  <p class="muted">No climate devices</p>
{:else}
  {#each climateDevices as device}
    <h2>{device.name} ({device.zone})</h2>
    {@const devReadings = readings.get(device.id) ?? []}

    <p>
      Latest &mdash; Temp: {fmt(latestByMetric(devReadings, 'temperature'))} C
      | RH: {fmt(latestByMetric(devReadings, 'humidity'))} %
      | VPD: {fmt(latestByMetric(devReadings, 'vpd'), 2)} kPa
    </p>

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
  {/each}
{/if}
