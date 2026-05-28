<script lang="ts">
  import { get } from '$lib/api.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { toTimeseries, type TimeseriesPoint } from '$lib/types.js';
  import { onMount } from 'svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import type uPlot from 'uplot';

  // ── Types ──────────────────────────────────────────────────────────────────
  interface MetricGroup {
    deviceType: string;
    label: string;
    metrics: string[];
    deviceIds: string[];
  }

  // ── State ──────────────────────────────────────────────────────────────────
  let devices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());
  let activeMetrics = $state<Set<string>>(new Set());
  let loadingDevices = $state<Set<string>>(new Set());

  // Shared crosshair: all active uPlot instances
  let activeCharts: uPlot[] = [];
  let cursorSyncing = false;

  const sharedCursorHooks: uPlot.Hooks.Arrays = {
    setCursor: [(u: uPlot) => {
      if (cursorSyncing) return;
      const left = u.cursor.left ?? -1;
      const top = u.cursor.top ?? 0;
      if (left < 0) return;
      cursorSyncing = true;
      for (const other of activeCharts) {
        if (other !== u) {
          try { other.setCursor({ left, top }); } catch { /* destroyed */ }
        }
      }
      cursorSyncing = false;
    }],
  };

  // ── Source mapping ─────────────────────────────────────────────────────────
  const SOURCE_MAP: Record<string, string> = {
    shelly_plug: 'shelly',
    shelly_relay: 'shelly',
    shelly_dimmer: 'shelly',
    blu_ht: 'blu_ht',
    ecowitt_soil: 'ecowitt',
    ecowitt_indoor: 'ecowitt',
  };

  // ── Device-type grouping ───────────────────────────────────────────────────
  const TYPE_META: Record<string, { label: string; metrics: string[] }> = {
    blu_ht:         { label: 'BLU H+T',        metrics: ['temperature', 'humidity', 'vpd', 'battery'] },
    ecowitt_indoor: { label: 'Ecowitt Indoor',  metrics: ['temperature', 'humidity', 'pressure'] },
    ecowitt_soil:   { label: 'Soil Channels',   metrics: ['moisture', 'battery'] },
    shelly_plug:    { label: 'Shelly Plugs',    metrics: ['power', 'energy', 'temperature'] },
    shelly_relay:   { label: 'Shelly Relays',   metrics: [] },
    shelly_dimmer:  { label: 'Shelly Dimmers',  metrics: ['power'] },
  };

  // ── Series colours ─────────────────────────────────────────────────────────
  const STROKES = [
    'oklch(82% 0.14 145)',
    'oklch(72% 0.15 220)',
    'oklch(78% 0.16 75)',
    'oklch(68% 0.22 25)',
    'oklch(70% 0.24 320)',
    'oklch(85% 0.16 95)',
    'oklch(75% 0.15 270)',
    'oklch(72% 0.14 185)',
  ];
  const FILLS = STROKES.map(s => s.replace(')', ' / 0.10)'));

  // ── Metric groups (derived from loaded devices) ────────────────────────────
  let metricGroups = $derived.by(() => {
    const typeMap = new Map<string, { devices: Device[]; metrics: Set<string> }>();

    for (const d of devices) {
      const meta = TYPE_META[d.device_type];
      if (!meta || meta.metrics.length === 0) continue;
      if (!typeMap.has(d.device_type)) {
        typeMap.set(d.device_type, { devices: [], metrics: new Set(meta.metrics) });
      }
      typeMap.get(d.device_type)!.devices.push(d);
    }

    const groups: MetricGroup[] = [];
    for (const [type, { devices: devs, metrics }] of typeMap) {
      groups.push({
        deviceType: type,
        label: TYPE_META[type]?.label ?? type,
        metrics: [...metrics],
        deviceIds: devs.map(d => d.id),
      });
    }
    return groups;
  });

  // ── Active metric key = "deviceType:metric" ────────────────────────────────
  function metricKey(deviceType: string, metric: string): string {
    return `${deviceType}:${metric}`;
  }

  // ── Toggle a metric ────────────────────────────────────────────────────────
  async function toggleMetric(deviceType: string, metric: string) {
    const key = metricKey(deviceType, metric);
    const next = new Set(activeMetrics);

    if (next.has(key)) {
      next.delete(key);
      activeMetrics = next;
      return;
    }

    next.add(key);
    activeMetrics = next;

    // Load readings for any devices of this type that aren't loaded yet
    const group = metricGroups.find(g => g.deviceType === deviceType);
    if (!group) return;

    const toLoad = group.deviceIds.filter(id => !readings.has(id));
    if (!toLoad.length) return;

    const loading = new Set(loadingDevices);
    for (const id of toLoad) loading.add(id);
    loadingDevices = loading;

    const results = await Promise.allSettled(
      toLoad.map(async id => {
        const res = await get<ReadingsResponse>(`/api/readings/${id}?limit=100`);
        return { id, data: res.readings };
      })
    );

    // Atomic update: one state write instead of one per device (prevents race)
    const nextReadings = new Map(readings);
    for (const r of results) {
      if (r.status === 'fulfilled') nextReadings.set(r.value.id, r.value.data);
    }
    readings = nextReadings;

    const done = new Set(loadingDevices);
    for (const id of toLoad) done.delete(id);
    loadingDevices = done;
  }

  // ── Build chart data for a given metric key ───────────────────────────────
  function buildChartData(key: string): { data: uPlot.AlignedData; series: uPlot.Series[]; unit: string } {
    const [deviceType, metric] = key.split(':');
    const group = metricGroups.find(g => g.deviceType === deviceType);
    if (!group) return { data: [[]] as unknown as uPlot.AlignedData, series: [{}], unit: '' };

    const allTs = new Set<number>();
    const devMaps: { id: string; name: string; m: Map<number, number> }[] = [];

    for (const id of group.deviceIds) {
      const m = new Map<number, number>();
      for (const r of readings.get(id) ?? []) {
        if (r.metric === metric) {
          const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
          allTs.add(ts);
          m.set(ts, r.value);
        }
      }
      if (m.size) {
        const dev = devices.find(d => d.id === id);
        devMaps.push({ id, name: dev?.name ?? id, m });
      }
    }

    const xs = [...allTs].sort((a, b) => a - b);
    const series: uPlot.Series[] = [{}];
    const ys: (number | null)[][] = [];

    devMaps.forEach(({ name, m }, i) => {
      series.push({
        label: name,
        stroke: STROKES[i % STROKES.length],
        fill: FILLS[i % FILLS.length],
        width: 1.5,
        spanGaps: false,
      });
      ys.push(xs.map(t => m.get(t) ?? null));
    });

    const UNITS: Record<string, string> = {
      temperature: '°C', humidity: '%', vpd: 'kPa', pressure: 'hPa',
      moisture: '%', power: 'W', energy: 'kWh', battery: 'V',
    };

    return {
      data: [xs, ...ys] as uPlot.AlignedData,
      series,
      unit: UNITS[metric] ?? '',
    };
  }

  // ── Active chart list (derived from activeMetrics) ─────────────────────────
  let activeChartKeys = $derived([...activeMetrics]);

  // ── Correlation table (re-used from original, adapted) ────────────────────
  let allPoints = $derived.by(() => {
    const points: TimeseriesPoint[] = [];
    for (const [id, devReadings] of readings) {
      const device = devices.find(d => d.id === id);
      if (!device) continue;
      const source = SOURCE_MAP[device.device_type] ?? 'unknown';
      for (const r of devReadings) {
        const key = metricKey(device.device_type, r.metric);
        if (activeMetrics.has(key)) {
          points.push(toTimeseries(r, source));
        }
      }
    }
    return points.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
  });

  const correlationRows = $derived.by(() => {
    const selectedDevices = new Set(
      [...activeMetrics].flatMap(key => {
        const [type] = key.split(':');
        return metricGroups.find(g => g.deviceType === type)?.deviceIds ?? [];
      })
    );
    if (selectedDevices.size < 2) return { columns: [] as string[], rows: [] as { timestamp: string; values: (number | null)[] }[] };

    const buckets = new Map<string, Map<string, number>>();
    for (const p of allPoints) {
      const ts = new Date(p.timestamp);
      ts.setSeconds(Math.round(ts.getSeconds() / 30) * 30, 0);
      const key = ts.toISOString();
      if (!buckets.has(key)) buckets.set(key, new Map());
      const label = `${p.device_id}:${p.metric}`;
      buckets.get(key)!.set(label, p.value);
    }

    const columns = [...new Set(allPoints.map(p => `${p.device_id}:${p.metric}`))].sort();
    const rows = [...buckets.entries()]
      .sort((a, b) => b[0].localeCompare(a[0]))
      .slice(0, 30)
      .map(([ts, vals]) => ({
        timestamp: ts,
        values: columns.map(col => vals.get(col) ?? null),
      }));

    return { columns, rows } as { columns: string[]; rows: { timestamp: string; values: (number | null)[] }[] };
  });

  // ── Load devices on mount ─────────────────────────────────────────────────
  onMount(async () => {
    const res = await get<StatusResponse>('/api/status');
    devices = res.devices;
  });

  function labelMetric(metric: string): string {
    const MAP: Record<string, string> = {
      temperature: 'Temperature', humidity: 'Humidity', vpd: 'VPD',
      pressure: 'Pressure', moisture: 'Soil moisture', power: 'Power',
      energy: 'Energy', battery: 'Battery', rssi: 'RSSI',
    };
    return MAP[metric] ?? metric;
  }
</script>

<div class="page">

  <!-- ── Layout: sidebar + main ─────────────────────────────────────────────── -->
  <div class="layout">

    <!-- ── Layer panel (left sidebar) ──────────────────────────────────────── -->
    <aside class="layer-panel">
      <div class="panel-header">Layer</div>

      {#if metricGroups.length === 0}
        <div class="panel-empty">Loading devices…</div>
      {:else}
        {#each metricGroups as group (group.deviceType)}
          <div class="metric-group">
            <div class="group-label">{group.label}</div>
            <div class="metric-buttons">
              {#each group.metrics as metric}
                {@const key = metricKey(group.deviceType, metric)}
                {@const active = activeMetrics.has(key)}
                {@const isLoading = active && group.deviceIds.some(id => loadingDevices.has(id))}
                <button
                  class="metric-btn"
                  class:active
                  class:loading={isLoading}
                  onclick={() => toggleMetric(group.deviceType, metric)}
                >
                  {#if active}
                    <span class="btn-dot"></span>
                  {/if}
                  {labelMetric(metric)}
                </button>
              {/each}
            </div>
          </div>
        {/each}
      {/if}
    </aside>

    <!-- ── Chart area (right) ─────────────────────────────────────────────── -->
    <div class="chart-area">

      {#if activeChartKeys.length === 0}
        <div class="chart-empty">
          <div class="empty-icon">◎</div>
          <p>Select a metric in the Layer panel</p>
          <p class="empty-sub">Multiple metrics generate synchronized charts</p>
        </div>
      {:else}
        {#each activeChartKeys as key (key)}
          {@const [deviceType, metric] = key.split(':')}
          {@const chart = buildChartData(key)}
          <section class="chart-section">
            <header class="section-header">
              <span class="section-label">{labelMetric(metric)}</span>
              {#if chart.unit}
                <span class="section-unit">{chart.unit}</span>
              {/if}
              <span class="section-device-type">{TYPE_META[deviceType]?.label ?? deviceType}</span>
              <button
                class="remove-btn"
                onclick={() => toggleMetric(deviceType, metric)}
                aria-label="Remove layer"
              >✕</button>
            </header>
            <TimeChart
              data={chart.data}
              series={chart.series}
              height={180}
              hooks={sharedCursorHooks}
              onready={(u) => { activeCharts.push(u); }}
              ondestroy={() => { activeCharts = activeCharts.filter(c => {
                try { c.root; return true; } catch { return false; }
              }); }}
            />
          </section>
        {/each}

        <!-- ── Correlation table ──────────────────────────────────────────── -->
        {#if correlationRows.columns.length >= 2}
          <section class="corr-section">
            <header class="section-header">
              <span class="section-label">Correlation</span>
              <span class="section-unit">30s-Buckets</span>
            </header>
            <div class="corr-table-wrap">
              <table class="corr-table">
                <thead>
                  <tr>
                    <th>Time</th>
                    {#each correlationRows.columns as col}
                      <th>{col}</th>
                    {/each}
                  </tr>
                </thead>
                <tbody>
                  {#each correlationRows.rows as row}
                    <tr>
                      <td class="ts-cell">{new Date(row.timestamp).toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}</td>
                      {#each row.values as v}
                        <td class:null-cell={v === null}>{v !== null ? v : '—'}</td>
                      {/each}
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          </section>
        {/if}

      {/if}
    </div>

  </div>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  /* ── Main layout ───────────────────────────────────────────────────────────── */
  .layout {
    display: grid;
    grid-template-columns: 220px 1fr;
    gap: var(--s-4);
    align-items: start;
    min-height: 100%;
  }

  /* ── Layer panel ───────────────────────────────────────────────────────────── */
  .layer-panel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    position: sticky;
    top: var(--s-4);
  }

  .panel-header {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    padding-bottom: var(--s-2);
    border-bottom: 1px solid var(--line);
  }

  .panel-empty {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-4) 0;
  }

  .metric-group {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .group-label {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px 0;
  }

  .metric-buttons {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .metric-btn {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    width: 100%;
    padding: 5px var(--s-3);
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r-2);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-3);
    cursor: pointer;
    text-align: left;
    transition: background 0.1s, border-color 0.1s, color 0.1s;
  }

  .metric-btn:hover {
    background: var(--bg-2);
    color: var(--ink-2);
  }

  .metric-btn.active {
    background: var(--accent-soft);
    border-color: var(--accent-line);
    color: var(--ink-1);
  }

  .metric-btn.loading {
    opacity: 0.7;
  }

  .btn-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--accent);
    flex-shrink: 0;
  }

  /* ── Chart area ────────────────────────────────────────────────────────────── */
  .chart-area {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    min-width: 0;
  }

  .chart-empty {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: var(--s-3);
    padding: var(--s-12) 0;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
  }

  .empty-icon {
    font-size: var(--t-32);
    color: var(--ink-4);
    line-height: 1;
  }

  .chart-empty p {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-3);
    margin: 0;
    text-align: center;
  }

  .empty-sub {
    font-size: var(--t-10) !important;
    color: var(--ink-4) !important;
  }

  .chart-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .section-header {
    display: flex;
    align-items: baseline;
    gap: var(--s-3);
  }

  .section-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .section-unit {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
  }

  .section-device-type {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-pill);
    padding: 1px 6px;
  }

  .remove-btn {
    margin-left: auto;
    background: transparent;
    border: none;
    color: var(--ink-4);
    font-size: var(--t-10);
    cursor: pointer;
    padding: 2px 6px;
    border-radius: var(--r-2);
    transition: background 0.1s, color 0.1s;
    line-height: 1;
  }

  .remove-btn:hover {
    background: var(--st-crit-soft);
    color: var(--st-crit);
  }

  /* ── Correlation table ─────────────────────────────────────────────────────── */
  .corr-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .corr-table-wrap {
    overflow-x: auto;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
  }

  .corr-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--t-10);
  }

  .corr-table th {
    padding: var(--s-2) var(--s-3);
    text-align: right;
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    font-size: var(--t-9);
    border-bottom: 1px solid var(--line);
    background: var(--bg-2);
    white-space: nowrap;
  }

  .corr-table th:first-child {
    text-align: left;
  }

  .corr-table td {
    padding: var(--s-1) var(--s-3);
    text-align: right;
    color: var(--ink-2);
    border-bottom: 1px solid var(--line);
    font-variant-numeric: tabular-nums;
  }

  .corr-table td:first-child {
    text-align: left;
  }

  .corr-table tr:last-child td {
    border-bottom: none;
  }

  .corr-table tr:hover td {
    background: var(--bg-2);
  }

  .ts-cell {
    white-space: nowrap;
    color: var(--ink-4) !important;
  }

  .null-cell {
    color: var(--ink-4) !important;
  }
</style>
