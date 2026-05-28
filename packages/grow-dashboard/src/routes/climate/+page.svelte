<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';
  import KPI from '$lib/components/KPI.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import type uPlot from 'uplot';

  // ── State ────────────────────────────────────────────────────────────────────
  let devices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());
  let loading = $state(true);

  // ── Series colours (8 slots) ─────────────────────────────────────────────────
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

  // ── Data loading ─────────────────────────────────────────────────────────────
  async function load() {
    const status = await get<StatusResponse>('/api/status');
    devices = status.devices.filter(
      d => d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor'
    );

    const map = new Map<string, SensorReading[]>();
    await Promise.all(
      devices.map(async d => {
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
    if (evt?.type === 'sensor_update') {
      const src = evt.data.source as string;
      if (src === 'blu_ht' || src === 'ecowitt') load();
    }
  });

  // ── KPI helpers ──────────────────────────────────────────────────────────────
  function latestVal(id: string, metric: string): number | null {
    const r = readings.get(id)?.find(r => r.metric === metric);
    return r?.value ?? null;
  }

  let temp = $derived.by(() => {
    for (const d of devices) {
      const v = latestVal(d.id, 'temperature');
      if (v !== null) return v;
    }
    return null;
  });

  let rh = $derived.by(() => {
    for (const d of devices) {
      const v = latestVal(d.id, 'humidity');
      if (v !== null) return v;
    }
    return null;
  });

  let vpd = $derived.by(() => {
    for (const d of devices) {
      const v = latestVal(d.id, 'vpd');
      if (v !== null) return v;
    }
    return null;
  });

  function vpdStatus(v: number | null): 'ok' | 'warn' | 'crit' {
    if (v === null) return 'crit';
    if (v >= 0.8 && v <= 1.6) return 'ok';
    if (v > 1.6 || v < 0.5) return 'crit';
    return 'warn';
  }

  // ── Chart data builder ───────────────────────────────────────────────────────
  function buildMetricData(metric: string): { data: uPlot.AlignedData; series: uPlot.Series[] } {
    const allTs = new Set<number>();
    const devMaps: Map<string, Map<number, number>> = new Map();

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
    const uSeries: uPlot.Series[] = [{}]; // x descriptor
    const ys: (number | null)[][] = [];

    let colorIdx = 0;
    for (const [id, m] of devMaps) {
      const device = devices.find(d => d.id === id)!;
      uSeries.push({
        label: device.name,
        stroke: STROKES[colorIdx % STROKES.length],
        fill: FILLS[colorIdx % FILLS.length],
        width: 1.5,
        spanGaps: false,
      });
      ys.push(xs.map(t => m.get(t) ?? null));
      colorIdx++;
    }

    return {
      data: [xs, ...ys] as uPlot.AlignedData,
      series: uSeries,
    };
  }

  let tempChart = $derived(buildMetricData('temperature'));
  let rhChart = $derived(buildMetricData('humidity'));
  let vpdChart = $derived(buildMetricData('vpd'));

  // ── VPD band overlay ─────────────────────────────────────────────────────────
  const vpdHooks: uPlot.Hooks.Arrays = {
    draw: [(u) => {
      const ctx = u.ctx;
      ctx.save();

      const dpr = devicePixelRatio || 1;
      const left = u.bbox.left;
      const w = u.bbox.width;

      // Veg zone 0.8–1.2 kPa (green-soft)
      const vegTop = u.valToPos(1.2, 'y', true);
      const vegBot = u.valToPos(0.8, 'y', true);
      ctx.fillStyle = 'oklch(78% 0.16 145 / 0.13)';
      ctx.fillRect(left, vegTop, w, vegBot - vegTop);

      // Flower zone 1.2–1.6 kPa (amber-soft)
      const flowTop = u.valToPos(1.6, 'y', true);
      const flowBot = u.valToPos(1.2, 'y', true);
      ctx.fillStyle = 'oklch(78% 0.16 75 / 0.13)';
      ctx.fillRect(left, flowTop, w, flowBot - flowTop);

      // Zone labels
      ctx.font = `${10 * dpr}px JetBrains Mono`;
      ctx.fillStyle = 'oklch(78% 0.16 145 / 0.55)';
      ctx.fillText('VEG', left + 6 * dpr, vegBot - 5 * dpr);
      ctx.fillStyle = 'oklch(78% 0.16 75 / 0.55)';
      ctx.fillText('FLOWER', left + 6 * dpr, flowBot - 5 * dpr);

      ctx.restore();
    }],
  };

  function fmt(v: number | null, d = 1): string {
    return v !== null ? v.toFixed(d) : '—';
  }
</script>

<div class="page">

  <!-- ── KPI Strip ──────────────────────────────────────────────────────────── -->
  <div class="kpi-strip">
    <div class="kpi-group">
      <KPI label="Temperature" value={fmt(temp)} unit="°C" />
      <div class="kpi-sep"></div>
      <KPI label="Humidity" value={fmt(rh, 0)} unit="%" />
      <div class="kpi-sep"></div>
      <div class="kpi-vpd">
        <KPI label="VPD" value={fmt(vpd, 2)} unit="kPa" />
        <div class="vpd-dot">
          <StatusDot variant={vpdStatus(vpd)} live={vpd !== null} />
        </div>
      </div>
    </div>

    <div class="device-pills">
      {#each devices as d}
        <div class="device-pill">
          <StatusDot variant={d.status === 'online' ? 'ok' : 'crit'} live={d.status === 'online'} />
          <span class="pill-name">{d.name}</span>
          <span class="pill-zone">{d.zone}</span>
        </div>
      {/each}
    </div>
  </div>

  <!-- ── Charts ────────────────────────────────────────────────────────────── -->
  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading sensor data…</span>
    </div>
  {:else if devices.length === 0}
    <div class="empty">No climate sensors found</div>
  {:else}
    <section class="chart-section">
      <header class="section-header">
        <span class="section-label">Temperature</span>
        <span class="section-unit">°C</span>
      </header>
      <TimeChart
        data={tempChart.data}
        series={tempChart.series}
        height={180}
      />
    </section>

    <section class="chart-section">
      <header class="section-header">
        <span class="section-label">Humidity</span>
        <span class="section-unit">%</span>
      </header>
      <TimeChart
        data={rhChart.data}
        series={rhChart.series}
        height={180}
      />
    </section>

    <section class="chart-section">
      <header class="section-header">
        <span class="section-label">VPD</span>
        <span class="section-unit">kPa</span>
        <span class="section-hint">
          <span class="band-swatch ok"></span> Veg 0.8–1.2
          <span class="band-swatch warn"></span> Flower 1.2–1.6
        </span>
      </header>
      <TimeChart
        data={vpdChart.data}
        series={vpdChart.series}
        height={200}
        hooks={vpdHooks}
      />
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
    min-width: 120px;
  }

  .kpi-sep {
    width: 1px;
    background: var(--line);
    align-self: stretch;
    flex-shrink: 0;
  }

  .kpi-vpd {
    position: relative;
    display: flex;
  }

  .vpd-dot {
    position: absolute;
    top: var(--s-3);
    right: var(--s-3);
  }

  /* ── Device pills ──────────────────────────────────────────────────────────── */
  .device-pills {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2);
    align-items: center;
  }

  .device-pill {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-pill);
    padding: 4px var(--s-3);
  }

  .pill-name {
    font-size: var(--t-11);
    color: var(--ink-2);
    font-family: var(--font-sans);
    white-space: nowrap;
  }

  .pill-zone {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  /* ── Chart sections ────────────────────────────────────────────────────────── */
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

  .section-hint {
    margin-left: auto;
    display: flex;
    align-items: center;
    gap: 6px;
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
  }

  .band-swatch {
    display: inline-block;
    width: 10px;
    height: 10px;
    border-radius: 2px;
    flex-shrink: 0;
  }

  .band-swatch.ok   { background: var(--st-ok-soft); border: 1px solid var(--st-ok); }
  .band-swatch.warn { background: var(--st-warn-soft); border: 1px solid var(--st-warn); }

  /* ── Loading / empty states ────────────────────────────────────────────────── */
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
    border-radius: 1px;
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
