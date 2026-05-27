<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';

  let soilDevices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());

  async function load() {
    const status = await get<StatusResponse>('/api/status');
    soilDevices = status.devices.filter(d => d.device_type === 'ecowitt_soil');
    const map = new Map<string, SensorReading[]>();
    for (const d of soilDevices) {
      const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=5`);
      map.set(d.id, res.readings);
    }
    readings = map;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update' && evt.data.source === 'ecowitt') {
      load();
    }
  });

  function latest(deviceReadings: SensorReading[], metric: string): SensorReading | undefined {
    return deviceReadings.find(r => r.metric === metric);
  }
</script>

<h1>Soil Moisture</h1>

{#if soilDevices.length === 0}
  <p class="muted">No soil sensors</p>
{:else}
  <table>
    <thead>
      <tr><th>Channel</th><th>Zone</th><th>Moisture (%)</th><th>Battery</th><th>Last Update</th></tr>
    </thead>
    <tbody>
      {#each soilDevices as device}
        {@const devReadings = readings.get(device.id) ?? []}
        {@const moisture = latest(devReadings, 'moisture')}
        {@const battery = latest(devReadings, 'battery')}
        <tr>
          <td>{device.name}</td>
          <td>{device.zone}</td>
          <td>{moisture ? moisture.value + '%' : '\u2014'}</td>
          <td>{battery ? battery.value : '\u2014'}</td>
          <td>{moisture?.timestamp ?? '\u2014'}</td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}
