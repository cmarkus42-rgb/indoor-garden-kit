<script lang="ts">
  import { get } from '$lib/api.js';
  import { visibleDevices } from '$lib/visibility.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';
  import KPI from '$lib/components/KPI.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import type uPlot from 'uplot';

  // ── State ──────────────────────────────────────────────────────────────────
  let plugs = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());
  let loading = $state(true);

  const STROKES = [
    'oklch(82% 0.14 145)',
    'oklch(72% 0.15 220)',
    'oklch(78% 0.16 75)',
    'oklch(68% 0.22 25)',
    'oklch(70% 0.24 320)',
  ];
  const FILLS = STROKES.map(s => s.replace(')', ' / 0.15)'));

  // ── Load ────────────────────────────────────────────────────────────────────
  async function load() {
    const status = await get<StatusResponse>('/api/status');
    plugs = visibleDevices(status.devices, 'energy').filter(d => d.device_type === 'shelly_plug');

    const map = new Map<string, SensorReading[]>();
    await Promise.all(
      plugs.map(async d => {
        const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=100`);
        map.set(d.id, res.readings);
      })
    );
    readings = map;
    loading = false;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update' && evt.data.source === 'shelly') load();
  });

  // ── KPI helpers ─────────────────────────────────────────────────────────────
  function latestVal(id: string, metric: string): number | null {
    const r = readings.get(id)?.find(r => r.metric === metric);
    return r?.value ?? null;
  }

  let totalWatts = $derived.by(() => {
    if (!plugs.length) return null;
    let sum = 0;
    for (const p of plugs) {
      sum += latestVal(p.id, 'power') ?? 0;
    }
    return sum;
  });

  let totalKwh = $derived.by(() => {
    if (!plugs.length) return null;
    let sum = 0;
    for (const p of plugs) {
      sum += latestVal(p.id, 'energy') ?? 0;
    }
    return sum;
  });

  function fmt(v: number | null, d = 1): string {
    return v !== null ? v.toFixed(d) : '—';
  }

  // ── Power chart data ─────────────────────────────────────────────────────────
  // Individual (overlapping) filled series per plug — clearest for monitoring
  let powerChart = $derived.by(() => {
    const allTs = new Set<number>();
    const devMaps: { id: string; name: string; m: Map<number, number> }[] = [];

    for (const p of plugs) {
      const m = new Map<number, number>();
      for (const r of readings.get(p.id) ?? []) {
        if (r.metric === 'power') {
          const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
          allTs.add(ts);
          m.set(ts, r.value);
        }
      }
      if (m.size) devMaps.push({ id: p.id, name: p.name, m });
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

    return { data: [xs, ...ys] as uPlot.AlignedData, series };
  });

  // ── Plug table rows ──────────────────────────────────────────────────────────
  let plugRows = $derived(
    plugs.map((p, i) => ({
      plug: p,
      power: latestVal(p.id, 'power'),
      energy: latestVal(p.id, 'energy'),
      temp: latestVal(p.id, 'temperature'),
      color: STROKES[i % STROKES.length],
    }))
  );
</script>

<div class="page">

  <!-- ── KPI Strip ──────────────────────────────────────────────────────────── -->
  <div class="kpi-strip">
    <div class="kpi-group">
      <KPI label="Total Power" value={fmt(totalWatts, 0)} unit="W" />
      <div class="kpi-sep"></div>
      <KPI label="Energy today" value={fmt(totalKwh, 2)} unit="kWh" />
    </div>

    <div class="plug-pills">
      {#each plugs as p, i}
        <div class="plug-pill">
          <span class="plug-swatch" style="background: {STROKES[i % STROKES.length]}"></span>
          <StatusDot variant={p.status === 'online' ? 'ok' : 'crit'} live={p.status === 'online'} />
          <span class="pill-name">{p.name}</span>
        </div>
      {/each}
    </div>
  </div>

  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading energy data…</span>
    </div>
  {:else if plugs.length === 0}
    <div class="empty">No plugs found</div>
  {:else}

    <!-- ── Power chart ───────────────────────────────────────────────────────── -->
    <section class="chart-section">
      <header class="section-header">
        <span class="section-label">Power</span>
        <span class="section-unit">W</span>
      </header>
      <TimeChart
        data={powerChart.data}
        series={powerChart.series}
        height={220}
      />
    </section>

    <!-- ── Plug detail table ─────────────────────────────────────────────────── -->
    <section class="table-section">
      <header class="section-header">
        <span class="section-label">Plug Details</span>
      </header>

      <div class="plug-table">
        <div class="table-head">
          <span>Device</span>
          <span>Zone</span>
          <span class="num">Power</span>
          <span class="num">Energy</span>
          <span class="num">Temp</span>
          <span>Status</span>
        </div>

        {#each plugRows as row (row.plug.id)}
          <div class="table-row" class:offline={row.plug.status !== 'online'}>
            <span class="row-name">
              <span class="row-swatch" style="background: {row.color}"></span>
              {row.plug.name}
            </span>
            <span class="row-zone">{row.plug.zone}</span>
            <span class="row-num">{fmt(row.power, 0)} <small>W</small></span>
            <span class="row-num">{fmt(row.energy, 3)} <small>kWh</small></span>
            <span class="row-num">{fmt(row.temp)} <small>°C</small></span>
            <span>
              <StatusDot
                variant={row.plug.status === 'online' ? 'ok' : 'crit'}
                live={row.plug.status === 'online'}
              />
            </span>
          </div>
        {/each}
      </div>
    </section>

  {/if}

</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  /* ── KPI strip ─────────────────────────────────────────────────────────────── */
  .kpi-strip {
    display: flex;
    align-items: stretch;
    gap: var(--s-4);
  }

  .kpi-group {
    display: flex;
    align-items: stretch;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
    flex-shrink: 0;
  }

  .kpi-group :global(.kpi) {
    border: none;
    border-radius: 0;
    background: transparent;
    min-width: 140px;
  }

  .kpi-sep {
    width: 1px;
    background: var(--line);
    align-self: stretch;
    flex-shrink: 0;
  }

  /* ── Plug pills ────────────────────────────────────────────────────────────── */
  .plug-pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2);
    align-items: center;
  }

  .plug-pill {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-pill);
    padding: 4px var(--s-3);
  }

  .plug-swatch {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    opacity: 0.8;
  }

  .pill-name {
    font-size: var(--t-11);
    color: var(--ink-2);
    font-family: var(--font-sans);
    white-space: nowrap;
  }

  /* ── Chart section ─────────────────────────────────────────────────────────── */
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

  /* ── Table section ─────────────────────────────────────────────────────────── */
  .table-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .plug-table {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    overflow: hidden;
  }

  .table-head,
  .table-row {
    display: grid;
    grid-template-columns: 1.8fr 0.8fr 1fr 1fr 0.8fr 48px;
    align-items: center;
    gap: 0;
    padding: var(--s-2) var(--s-4);
  }

  .table-head {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid var(--line);
    background: var(--bg-2);
  }

  .table-head .num { text-align: right; }

  .table-row {
    border-bottom: 1px solid var(--line);
    transition: background 0.15s;
  }

  .table-row:last-child { border-bottom: none; }

  .table-row:hover { background: var(--bg-2); }

  .table-row.offline { opacity: 0.5; }

  .row-name {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    font-size: var(--t-12);
    color: var(--ink-1);
    font-family: var(--font-sans);
  }

  .row-swatch {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
    opacity: 0.8;
  }

  .row-zone {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .row-num {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    text-align: right;
  }

  .row-num small {
    font-size: var(--t-9);
    color: var(--ink-4);
    margin-left: 2px;
  }

  /* ── Loading / empty ───────────────────────────────────────────────────────── */
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-10) 0;
  }

  .loading-bar {
    width: 120px;
    height: 2px;
    background: var(--line);
    border-radius: 1px;
    overflow: hidden;
    position: relative;
  }

  .loading-bar::after {
    content: '';
    position: absolute;
    inset-block: 0;
    left: -40%;
    width: 40%;
    background: var(--accent);
    animation: slide 1.2s ease-in-out infinite;
  }

  @keyframes slide {
    to { left: 100%; }
  }

  .loading-text {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .empty {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-10) 0;
  }
</style>
