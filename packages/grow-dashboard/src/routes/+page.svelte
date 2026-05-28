<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';
  import KPI from '$lib/components/KPI.svelte';
  import DeviceTile from '$lib/components/DeviceTile.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import type uPlot from 'uplot';

  // ── State ──────────────────────────────────────────────────────────────
  let allDevices = $state<Device[]>([]);
  let readings  = $state<Map<string, SensorReading[]>>(new Map());
  let loading   = $state(true);
  let reloadTimer: ReturnType<typeof setTimeout> | null = null;

  // ── Device slices ───────────────────────────────────────────────────────
  let climateDevices = $derived(
    allDevices.filter(d => d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor')
  );
  let soilDevices = $derived(
    allDevices.filter(d => d.device_type === 'ecowitt_sensor')
  );
  let lightDevices = $derived(
    allDevices.filter(
      d => d.device_type === 'shelly_plug' || d.device_type === 'shelly_dimmer'
    )
  );

  // ── Latest value helper ─────────────────────────────────────────────────
  function latestVal(id: string, metric: string): number | null {
    const r = readings.get(id)?.find(r => r.metric === metric);
    return r?.value ?? null;
  }

  // ── Hero aggregates ─────────────────────────────────────────────────────
  let avgTemp = $derived.by(() => {
    const vals = climateDevices
      .map(d => latestVal(d.id, 'temperature'))
      .filter((v): v is number => v !== null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  });

  let avgRh = $derived.by(() => {
    const vals = climateDevices
      .map(d => latestVal(d.id, 'humidity'))
      .filter((v): v is number => v !== null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  });

  let avgVpd = $derived.by(() => {
    const vals = climateDevices
      .map(d => latestVal(d.id, 'vpd'))
      .filter((v): v is number => v !== null);
    return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
  });

  let avgMoisture = $derived.by(() => {
    const vals = soilDevices
      .map(d => latestVal(d.id, 'soil_moisture'))
      .filter((v): v is number => v !== null);
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null;
  });

  let totalPower = $derived.by(() => {
    const sum = lightDevices.reduce((acc, d) => acc + (latestVal(d.id, 'power') ?? 0), 0);
    return sum > 0 ? sum.toFixed(0) : null;
  });

  // ── Chart helpers ───────────────────────────────────────────────────────
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
  const FILLS = STROKES.map(s => s.replace(')', ' / 0.12)'));

  function buildChart(
    devices: Device[],
    metric: string
  ): { data: uPlot.AlignedData; series: uPlot.Series[] } {
    const allTs = new Set<number>();
    const devMaps = new Map<string, Map<number, number>>();
    for (const d of devices) {
      const m = new Map<number, number>();
      for (const r of readings.get(d.id) ?? []) {
        if (r.metric === metric) {
          const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
          allTs.add(ts);
          m.set(ts, r.value);
        }
      }
      if (m.size) devMaps.set(d.id, m);
    }
    const xs = [...allTs].sort((a, b) => a - b);
    const series: uPlot.Series[] = [{}];
    const ys: (number | null)[][] = [];
    let i = 0;
    for (const [id, m] of devMaps) {
      const device = devices.find(d => d.id === id);
      if (!device) continue;
      series.push({
        label: device.name,
        stroke: STROKES[i % STROKES.length],
        fill: FILLS[i % FILLS.length],
        width: 1.5,
        spanGaps: false,
      });
      ys.push(xs.map(t => m.get(t) ?? null));
      i++;
    }
    return { data: [xs, ...ys] as uPlot.AlignedData, series };
  }

  let tempChart     = $derived(buildChart(climateDevices, 'temperature'));
  let rhChart       = $derived(buildChart(climateDevices, 'humidity'));
  let moistureChart = $derived(buildChart(soilDevices, 'soil_moisture'));

  // ── Staleness helpers ───────────────────────────────────────────────────
  function formatTimeAgo(isoDate: string): string {
    const diffMin = Math.floor((Date.now() - new Date(isoDate).getTime()) / 60_000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return `${Math.floor(diffH / 24)}d ago`;
  }

  const STALE_MS = 10 * 60_000;

  const climateStale = $derived.by(() => {
    const bluDevices = climateDevices.filter(d => d.device_type === 'blu_ht');
    if (!bluDevices.length) return false;
    return bluDevices.every(d => Date.now() - new Date(d.last_seen).getTime() > STALE_MS);
  });

  // ── Status helpers ──────────────────────────────────────────────────────
  function vpdStatus(v: number | null): 'ok' | 'warn' | 'crit' {
    if (v === null) return 'crit';
    if (v >= 0.8 && v <= 1.6) return 'ok';
    if (v > 1.6 || v < 0.5) return 'crit';
    return 'warn';
  }

  function moistureStatus(v: number | null): 'ok' | 'warn' | 'crit' | 'offline' {
    if (v === null) return 'offline';
    if (v >= 30 && v <= 70) return 'ok';
    if (v < 15 || v > 85) return 'crit';
    return 'warn';
  }

  function fmt(v: number | null, d = 1): string {
    return v !== null ? v.toFixed(d) : '—';
  }

  // ── Data loading ────────────────────────────────────────────────────────
  async function load() {
    try {
      const status = await get<StatusResponse>('/api/status');
      allDevices = status.devices;
      const map = new Map<string, SensorReading[]>();
      await Promise.allSettled(
        status.devices.map(async d => {
          try {
            const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=100`);
            map.set(d.id, res.readings ?? []);
          } catch { /* device has no readings */ }
        })
      );
      readings = map;
    } catch { /* ignore load error */ }
    loading = false;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update' || evt?.type === 'device_status') {
      if (reloadTimer !== null) clearTimeout(reloadTimer);
      reloadTimer = setTimeout(() => { load(); }, 3000);
    }
  });
</script>

<div class="page">

  <!-- ── Hero Ring ─────────────────────────────────────────────────────── -->
  <div class="hero">
    <div class="hero-ring">
      <div class="hero-kpis">
        <div class="hero-kpi">
          <span class="hkpi-val">{fmt(avgTemp)}</span>
          <span class="hkpi-unit">°C</span>
          <span class="hkpi-label">Temp</span>
        </div>
        <div class="hero-kpi">
          <span class="hkpi-val">{fmt(avgRh, 0)}</span>
          <span class="hkpi-unit">%</span>
          <span class="hkpi-label">RH</span>
        </div>
        <div class="hero-kpi">
          <span
            class="hkpi-val"
            class:st-ok={vpdStatus(avgVpd) === 'ok'}
            class:st-warn={vpdStatus(avgVpd) === 'warn'}
            class:st-crit={vpdStatus(avgVpd) === 'crit'}
          >{fmt(avgVpd, 2)}</span>
          <span class="hkpi-unit">kPa</span>
          <span class="hkpi-label">VPD</span>
        </div>
        <div class="hero-kpi">
          <span class="hkpi-val">{avgMoisture ?? '—'}</span>
          <span class="hkpi-unit">%</span>
          <span class="hkpi-label">Soil Avg</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Climate Section ───────────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Climate</span>
      <div class="ov-pills">
        {#each climateDevices as d (d.id)}
          <span class="ov-pill">
            <StatusDot variant={d.status === 'online' ? 'ok' : 'crit'} live={d.status === 'online' && d.device_type !== 'blu_ht'} />
            {d.name}{#if d.device_type === 'blu_ht'} · {formatTimeAgo(d.last_seen)}{/if}
          </span>
        {/each}
      </div>
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if climateDevices.length === 0}
      <p class="ov-empty">No climate sensors</p>
    {:else}
      <div class="kpi-row" class:stale={climateStale}>
        <KPI label="Temperature" value={fmt(avgTemp)} unit="°C" />
        <KPI label="Humidity" value={fmt(avgRh, 0)} unit="%" />
        <KPI label="VPD" value={fmt(avgVpd, 2)} unit="kPa" />
      </div>
      <div class="chart-pair">
        <div class="chart-block">
          <div class="chart-label">Temperature · °C</div>
          <TimeChart data={tempChart.data} series={tempChart.series} height={140} />
        </div>
        <div class="chart-block">
          <div class="chart-label">Humidity · %</div>
          <TimeChart data={rhChart.data} series={rhChart.series} height={140} />
        </div>
      </div>
    {/if}
  </section>

  <!-- ── Soil Section ──────────────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Soil Moisture</span>
      {#if avgMoisture !== null}
        <span class="ov-avg">{avgMoisture}% avg</span>
      {/if}
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if soilDevices.length === 0}
      <p class="ov-empty">No soil sensors</p>
    {:else}
      <div class="soil-tiles">
        {#each soilDevices as d, i (d.id)}
          {@const moisture = latestVal(d.id, 'soil_moisture')}
          <div class="soil-cell">
            <DeviceTile
              label={d.name}
              sub={d.zone}
              metric={moisture !== null ? String(Math.round(moisture)) : '—'}
              unit="%"
              status={moistureStatus(moisture)}
            />
            <div class="moisture-bar-wrap">
              <div
                class="moisture-bar"
                style="width: {moisture !== null ? Math.min(100, moisture) : 0}%; background: {STROKES[i % STROKES.length]}"
              ></div>
            </div>
          </div>
        {/each}
      </div>
      <div class="chart-block">
        <div class="chart-label">History · % Vol.</div>
        <TimeChart data={moistureChart.data} series={moistureChart.series} height={160} />
      </div>
    {/if}
  </section>

  <!-- ── Light & Power Section ─────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Light & Power</span>
      {#if totalPower !== null}
        <span class="ov-avg">{totalPower} W total</span>
      {/if}
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if lightDevices.length === 0}
      <p class="ov-empty">No devices</p>
    {:else}
      <div class="light-tiles">
        {#each lightDevices as d (d.id)}
          {@const power = latestVal(d.id, 'power')}
          <DeviceTile
            label={d.name}
            sub={d.zone}
            metric={power !== null ? power.toFixed(0) : '—'}
            unit="W"
            status={d.status === 'online' ? 'ok' : 'offline'}
          />
        {/each}
      </div>
    {/if}
  </section>

</div>

<style>
  /* ── Page shell ──────────────────────────────────────────────────────── */
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-6);
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  /* ── Hero Ring ───────────────────────────────────────────────────────── */
  .hero {
    display: flex;
    justify-content: center;
    padding: var(--s-4) 0;
  }

  .hero-ring {
    width: 300px;
    height: 300px;
    border-radius: 50%;
    border: 1px solid var(--accent);
    box-shadow: 0 0 40px color-mix(in oklch, var(--accent) 20%, transparent),
                inset 0 0 24px color-mix(in oklch, var(--accent) 6%, transparent);
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--bg-1);
  }

  .hero-kpis {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-5) var(--s-8);
    padding: var(--s-4);
  }

  .hero-kpi {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
  }

  .hkpi-val {
    font-family: var(--font-mono);
    font-size: var(--t-24);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .hkpi-val.st-ok   { color: var(--st-ok); }
  .hkpi-val.st-warn { color: var(--st-warn); }
  .hkpi-val.st-crit { color: var(--st-crit); }

  .hkpi-unit {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .hkpi-label {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  /* ── Sections ────────────────────────────────────────────────────────── */
  .ov-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    padding: var(--s-4);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
  }

  .ov-section-header {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding-bottom: var(--s-3);
    border-bottom: 1px solid var(--line);
  }

  .ov-section-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    flex: 1;
  }

  .ov-avg {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-2);
    font-variant-numeric: tabular-nums;
  }

  .ov-pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2);
  }

  .ov-pill {
    display: flex;
    align-items: center;
    gap: var(--s-1);
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  /* ── KPI row ─────────────────────────────────────────────────────────── */
  .kpi-row {
    display: flex;
    gap: var(--s-3);
  }

  .kpi-row :global(.kpi) {
    flex: 1;
    min-width: 0;
  }

  .kpi-row.stale :global(.kpi-value),
  .kpi-row.stale :global(.kpi-unit) {
    color: var(--ink-4);
    opacity: 0.6;
  }

  /* ── Chart pair ──────────────────────────────────────────────────────── */
  .chart-pair {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-4);
  }

  .chart-block {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .chart-label {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  /* ── Soil tiles ──────────────────────────────────────────────────────── */
  .soil-tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: var(--s-3);
  }

  .soil-cell {
    display: flex;
    flex-direction: column;
    gap: 4px;
  }

  .moisture-bar-wrap {
    height: 3px;
    background: var(--bg-3);
    border-radius: var(--r-pill);
    overflow: hidden;
  }

  .moisture-bar {
    height: 100%;
    border-radius: var(--r-pill);
    transition: width 0.4s ease;
    opacity: 0.75;
  }

  /* ── Light tiles ─────────────────────────────────────────────────────── */
  .light-tiles {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: var(--s-3);
  }

  /* ── Loading / empty ─────────────────────────────────────────────────── */
  .ov-skeleton {
    height: 60px;
    background: var(--bg-2);
    border-radius: var(--r-2);
    animation: shimmer 1.4s ease-in-out infinite;
  }

  @keyframes shimmer {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.45; }
  }

  .ov-empty {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-4) 0;
    margin: 0;
  }

  /* ── Responsive ──────────────────────────────────────────────────────── */
  @media (max-width: 768px) {
    .hero-ring {
      width: 260px;
      height: 260px;
    }

    .hkpi-val {
      font-size: var(--t-20);
    }

    .chart-pair {
      grid-template-columns: 1fr;
    }
  }
</style>
