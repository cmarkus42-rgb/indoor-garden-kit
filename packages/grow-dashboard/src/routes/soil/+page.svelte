<script lang="ts">
  import { get } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading } from '$lib/types.js';
  import { onMount } from 'svelte';
  import DeviceTile from '$lib/components/DeviceTile.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import type uPlot from 'uplot';

  // ── State ─────────────────────────────────────────────────────────────────────
  let devices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());
  let loading = $state(true);

  // 8 distinct series colours for channels
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

  // ── Load ──────────────────────────────────────────────────────────────────────
  async function load() {
    const status = await get<StatusResponse>('/api/status');
    devices = status.devices.filter(d => d.device_type === 'ecowitt_sensor');

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
    if (
      (evt?.type === 'sensor_update' && evt.data.source === 'ecowitt') ||
      evt?.type === 'irrigation'
    ) {
      load();
    }
  });

  // ── Tile helpers ──────────────────────────────────────────────────────────────
  function latestVal(id: string, metric: string): number | null {
    const r = readings.get(id)?.find(r => r.metric === metric);
    return r?.value ?? null;
  }

  function moistureStatus(v: number | null): 'ok' | 'warn' | 'crit' | 'offline' {
    if (v === null) return 'offline';
    if (v >= 30 && v <= 70) return 'ok';
    if (v < 15 || v > 85) return 'crit';
    return 'warn';
  }

  // ── Chart data ─────────────────────────────────────────────────────────────────
  let moistureChart = $derived.by(() => {
    const allTs = new Set<number>();
    const devMaps: { id: string; name: string; m: Map<number, number> }[] = [];

    for (const d of devices) {
      const m = new Map<number, number>();
      for (const r of readings.get(d.id) ?? []) {
        if (r.metric === 'soil_moisture') {
          const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
          allTs.add(ts);
          m.set(ts, r.value);
        }
      }
      if (m.size) devMaps.push({ id: d.id, name: d.name, m });
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

  // ── Threshold hook (30 % dry / 60 % field capacity) ──────────────────────────
  const thresholdHooks: uPlot.Hooks.Arrays = {
    draw: [(u) => {
      const ctx = u.ctx;
      ctx.save();
      const dpr = devicePixelRatio || 1;
      const left = u.bbox.left;
      const right = left + u.bbox.width;

      function drawLine(val: number, color: string, label: string) {
        const y = u.valToPos(val, 'y', true);
        ctx.save();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1 * dpr;
        ctx.setLineDash([4 * dpr, 4 * dpr]);
        ctx.beginPath();
        ctx.moveTo(left, y);
        ctx.lineTo(right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.fillStyle = color;
        ctx.font = `${9 * dpr}px JetBrains Mono`;
        ctx.fillText(label, left + 4 * dpr, y - 3 * dpr);
        ctx.restore();
      }

      drawLine(30, 'oklch(78% 0.16 75 / 0.7)', '30%');  // dry threshold (amber)
      drawLine(60, 'oklch(78% 0.16 145 / 0.7)', '60%'); // field capacity (green)

      ctx.restore();
    }],
  };

  function fmt(v: number | null, d = 0): string {
    return v !== null ? v.toFixed(d) : '—';
  }

  // Average moisture across all channels
  let avgMoisture = $derived.by(() => {
    const vals = devices
      .map(d => latestVal(d.id, 'soil_moisture'))
      .filter((v): v is number => v !== null);
    if (!vals.length) return null;
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  });
</script>

<div class="page">

  <!-- ── Summary header ─────────────────────────────────────────────────────── -->
  <div class="summary-bar">
    <div class="summary-label">Soil moisture</div>
    {#if avgMoisture !== null}
      <div class="summary-avg">
        <span class="avg-val">{avgMoisture}</span>
        <span class="avg-unit">% Ø</span>
      </div>
    {/if}
    <div class="threshold-legend">
      <span class="th-item warn">— 30% dry</span>
      <span class="th-item ok">— 60% field capacity</span>
    </div>
  </div>

  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading sensor data…</span>
    </div>
  {:else if devices.length === 0}
    <div class="empty">No soil sensors found</div>
  {:else}

    <!-- ── Tile grid 2×4 ────────────────────────────────────────────────────── -->
    <div class="tile-grid">
      {#each devices as d, i (d.id)}
        {@const moisture = latestVal(d.id, 'soil_moisture')}
        {@const battery = latestVal(d.id, 'battery')}
        <div class="tile-cell">
          <DeviceTile
            label={d.name}
            sub={`${d.zone} · bat ${fmt(battery, 1)}V`}
            metric={fmt(moisture)}
            unit="%"
            status={moistureStatus(moisture)}
            periodic={true}
            lastSeen={d.last_seen}
          />
          <!-- Moisture mini-bar -->
          <div class="moisture-bar-wrap">
            <div
              class="moisture-bar"
              style="width: {moisture !== null ? Math.min(100, moisture) : 0}%; background: {STROKES[i % STROKES.length]}"
              class:dry={moisture !== null && moisture < 30}
              class:wet={moisture !== null && moisture > 70}
            ></div>
          </div>
        </div>
      {/each}
    </div>

    <!-- ── History chart ──────────────────────────────────────────────────────── -->
    <section class="chart-section">
      <header class="section-header">
        <span class="section-label">Soil moisture history</span>
        <span class="section-unit">% Vol.</span>
      </header>
      <TimeChart
        data={moistureChart.data}
        series={moistureChart.series}
        height={240}
        hooks={thresholdHooks}
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

  /* ── Summary bar ───────────────────────────────────────────────────────────── */
  .summary-bar {
    display: flex;
    align-items: baseline;
    gap: var(--s-4);
    padding-bottom: var(--s-2);
    border-bottom: 1px solid var(--line);
  }

  .summary-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .summary-avg {
    display: flex;
    align-items: baseline;
    gap: 3px;
  }

  .avg-val {
    font-family: var(--font-mono);
    font-size: var(--t-20);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .avg-unit {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
  }

  .threshold-legend {
    margin-left: auto;
    display: flex;
    gap: var(--s-4);
    font-family: var(--font-mono);
    font-size: var(--t-9);
  }

  .th-item.warn { color: var(--st-warn); }
  .th-item.ok   { color: var(--st-ok); }

  /* ── Tile grid 2×4 ─────────────────────────────────────────────────────────── */
  .tile-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: var(--s-3);
  }

  .tile-cell {
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
