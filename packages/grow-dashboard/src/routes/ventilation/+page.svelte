<script lang="ts">
  import { get, post, del } from '$lib/api.js';
  import { visibleDevices } from '$lib/visibility.js';
  import { sseLatest } from '$lib/sse.js';
  import type { StatusResponse, ReadingsResponse, Device, SensorReading, WindStatusResponse } from '$lib/types.js';
  import { onMount } from 'svelte';
  import KPI from '$lib/components/KPI.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import type uPlot from 'uplot';

  // ── State ────────────────────────────────────────────────────────────────────
  let devices = $state<Device[]>([]);
  let readings = $state<Map<string, SensorReading[]>>(new Map());
  let wind = $state<WindStatusResponse | null>(null);
  let loading = $state(true);
  let overrideSpeed = $state(5);
  let overrideMinutes = $state(30);

  const SCENARIO_LABELS: Record<string, { label: string; icon: string; color: string }> = {
    calm:     { label: 'Calm',     icon: '○',  color: 'var(--st-ok)' },
    breeze:   { label: 'Breeze',   icon: '◐',  color: 'oklch(75% 0.15 220)' },
    moderate: { label: 'Moderate', icon: '◑',  color: 'var(--st-warn)' },
    stormy:   { label: 'Stormy',   icon: '●',  color: 'var(--st-crit)' },
    none:     { label: 'Off',      icon: '○',  color: 'var(--ink-4)' },
    unknown:  { label: '—',        icon: '?',  color: 'var(--ink-4)' },
  };

  const STROKES = [
    'oklch(82% 0.14 145)',
    'oklch(72% 0.15 220)',
    'oklch(78% 0.16 75)',
    'oklch(68% 0.22 25)',
  ];
  const FILLS = STROKES.map(s => s.replace(')', ' / 0.12)'));

  // ── Data loading ───────────────────────────────────────────────────────────
  async function load() {
    const [status, windRes] = await Promise.all([
      get<StatusResponse>('/api/status'),
      get<WindStatusResponse>('/api/wind/status').catch(() => null),
    ]);

    devices = visibleDevices(status.devices, 'ventilation').filter(d => d.device_type === 'ac_infinity');

    const map = new Map<string, SensorReading[]>();
    await Promise.all(
      devices.map(async d => {
        const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=120`);
        map.set(d.id, res.readings);
      })
    );
    readings = map;
    wind = windRes;
    loading = false;
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (!evt) return;
    if (evt.type === 'sensor_update' && evt.data.source === 'ac_infinity') load();
    if (evt.type === 'wind_update') load();
  });

  // ── KPI helpers ────────────────────────────────────────────────────────────
  function latestVal(id: string, metric: string): number | null {
    const arr = readings.get(id);
    if (!arr) return null;
    const r = arr.find(r => r.metric === metric);
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

  // ── Per-device port data ────────────────────────────────────────────────────
  function getPortSpeeds(deviceId: string): { port: number; speed: number; active: boolean }[] {
    const arr = readings.get(deviceId) ?? [];
    const ports: Map<number, { speed: number; active: boolean }> = new Map();
    for (const r of arr) {
      const sm = r.metric.match(/^fan_speed_port(\d+)$/);
      if (sm) {
        const p = parseInt(sm[1]);
        const existing = ports.get(p) ?? { speed: 0, active: false };
        existing.speed = r.value;
        ports.set(p, existing);
      }
      const am = r.metric.match(/^fan_active_port(\d+)$/);
      if (am) {
        const p = parseInt(am[1]);
        const existing = ports.get(p) ?? { speed: 0, active: false };
        existing.active = r.value > 0;
        ports.set(p, existing);
      }
    }
    return [...ports.entries()]
      .sort(([a], [b]) => a - b)
      .map(([port, data]) => ({ port, ...data }));
  }

  function getDevScenario(device: Device): string {
    if (!wind?.devices) return 'none';
    const devId = device.name;  // wind status keys by device name
    for (const [id, ds] of Object.entries(wind.devices)) {
      // Match by dev_id substring in the key
      if (devId.includes('schrank') && id.includes('schrank')) return ds.scenario;
      if (devId.includes('zelt') && id.includes('zelt')) return ds.scenario;
    }
    // fallback: iterate all
    for (const ds of Object.values(wind.devices)) {
      return ds.scenario;
    }
    return 'none';
  }

  // ── Chart builder ──────────────────────────────────────────────────────────
  function buildFanChart(deviceId: string): { data: uPlot.AlignedData; series: uPlot.Series[] } {
    const arr = readings.get(deviceId) ?? [];
    const portMetrics = new Map<string, Map<number, number>>();
    const allTs = new Set<number>();

    for (const r of arr) {
      if (r.metric.startsWith('fan_speed_port') || r.metric.startsWith('wind_target_port')) {
        const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
        allTs.add(ts);
        if (!portMetrics.has(r.metric)) portMetrics.set(r.metric, new Map());
        portMetrics.get(r.metric)!.set(ts, r.value);
      }
    }

    const xs = [...allTs].sort((a, b) => a - b);
    const uSeries: uPlot.Series[] = [{}];
    const ys: (number | null)[][] = [];

    let colorIdx = 0;
    for (const [metric, m] of portMetrics) {
      const isTarget = metric.startsWith('wind_target');
      uSeries.push({
        label: metric.replace(/_/g, ' '),
        stroke: STROKES[colorIdx % STROKES.length],
        fill: isTarget ? undefined : FILLS[colorIdx % FILLS.length],
        width: isTarget ? 1 : 1.5,
        dash: isTarget ? [4, 4] : undefined,
        spanGaps: false,
      });
      ys.push(xs.map(t => m.get(t) ?? null));
      if (!isTarget) colorIdx++;
    }

    return { data: [xs, ...ys] as uPlot.AlignedData, series: uSeries };
  }

  // ── Override actions ───────────────────────────────────────────────────────
  async function setOverride() {
    await post('/api/wind/override', { speed: overrideSpeed, duration_minutes: overrideMinutes });
    load();
  }

  async function clearOverride() {
    await del('/api/wind/override');
    load();
  }

  function fmt(v: number | null, d = 1): string {
    return v !== null ? v.toFixed(d) : '—';
  }

  function formatTimeAgo(iso: string): string {
    const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
  }
</script>

<div class="page">

  <!-- ── KPI Strip ─────────────────────────────────────────────────────────── -->
  <div class="kpi-strip">
    <div class="kpi-group">
      <KPI label="Temperature" value={fmt(temp)} unit="°C" />
      <div class="kpi-sep"></div>
      <KPI label="Humidity" value={fmt(rh, 0)} unit="%" />
      <div class="kpi-sep"></div>
      <KPI label="VPD" value={fmt(vpd, 2)} unit="kPa" />
    </div>

    {#if wind}
      <div class="wind-badge" class:override={wind.override_active}>
        {#if wind.override_active}
          <span class="badge-icon">⏸</span>
          <span class="badge-label">Override</span>
        {:else}
          <span class="badge-label">Wind Engine</span>
          <StatusDot variant="ok" />
        {/if}
      </div>
    {/if}
  </div>

  <!-- ── Device Tiles ─────────────────────────────────────────────────────── -->
  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading ventilation data…</span>
    </div>
  {:else if devices.length === 0}
    <div class="empty">No AC Infinity controllers found</div>
  {:else}
    {#each devices as device}
      {@const ports = getPortSpeeds(device.id)}
      {@const scenario = getDevScenario(device)}
      {@const scenarioInfo = SCENARIO_LABELS[scenario] ?? SCENARIO_LABELS['unknown']}
      {@const isOffline = device.status !== 'online'}

      <section class="controller-card" class:offline={isOffline}>
        {#if isOffline}
          <div class="offline-overlay" aria-hidden="true"></div>
        {/if}

        <header class="controller-header">
          <div class="controller-name">
            <StatusDot variant={isOffline ? 'crit' : 'ok'} />
            <span>{device.name}</span>
            <span class="controller-seen">{formatTimeAgo(device.last_seen)}</span>
          </div>
          <div class="scenario-chip" style:color={scenarioInfo.color}>
            <span class="scenario-icon">{scenarioInfo.icon}</span>
            <span>{scenarioInfo.label}</span>
          </div>
        </header>

        <div class="port-grid">
          {#each ports as p}
            <div class="port-row">
              <span class="port-label">Port {p.port}</span>
              <div class="speed-bar-track">
                <div class="speed-bar-fill" style:width="{p.speed * 10}%"
                     class:active={p.active}></div>
              </div>
              <span class="speed-value">{p.speed}<span class="speed-max">/10</span></span>
            </div>
          {/each}
        </div>

        <!-- Fan Speed Chart -->
        {#if !isOffline}
          {@const chart = buildFanChart(device.id)}
          {#if chart.data[0].length > 1}
            <div class="chart-wrap">
              <header class="section-header">
                <span class="section-label">Fan Speed</span>
                <span class="section-unit">0–10</span>
              </header>
              <TimeChart data={chart.data} series={chart.series} height={140} />
            </div>
          {/if}
        {:else}
          <div class="offline-note">
            Last: {fmt(latestVal(device.id, 'temperature'))}°C
            / {fmt(latestVal(device.id, 'humidity'), 0)}% RH
          </div>
        {/if}
      </section>
    {/each}

    <!-- ── Override Controls ────────────────────────────────────────────────── -->
    {#if wind}
      <section class="override-section">
        <header class="section-header">
          <span class="section-label">Manual Override</span>
        </header>

        {#if wind.override_active}
          <div class="override-active">
            <span>Override active — all fans locked</span>
            <button class="btn-clear" onclick={clearOverride}>Clear Override</button>
          </div>
        {:else}
          <div class="override-form">
            <div class="override-row">
              <label class="override-label">Speed</label>
              <input type="range" class="override-slider" min="0" max="10" bind:value={overrideSpeed} />
              <span class="override-val">{overrideSpeed}</span>
            </div>
            <div class="override-row">
              <label class="override-label">Duration</label>
              <select class="override-select" bind:value={overrideMinutes}>
                <option value={15}>15 min</option>
                <option value={30}>30 min</option>
                <option value={60}>1 hour</option>
                <option value={120}>2 hours</option>
              </select>
            </div>
            <button class="btn-override" onclick={setOverride}>Set Override</button>
          </div>
        {/if}
      </section>
    {/if}
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

  /* ── KPI strip ──────────────────────────────────────────────────────────── */
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
    min-width: 110px;
  }

  .kpi-sep {
    width: 1px;
    background: var(--line);
    align-self: stretch;
    flex-shrink: 0;
  }

  .wind-badge {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-pill);
    padding: var(--s-2) var(--s-4);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-2);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    align-self: center;
  }

  .wind-badge.override {
    border-color: var(--st-warn);
    color: var(--st-warn);
  }

  .badge-icon { font-size: var(--t-12); }

  /* ── Controller card ────────────────────────────────────────────────────── */
  .controller-card {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
    overflow: hidden;
  }

  .controller-card.offline { opacity: 0.7; }

  .offline-overlay {
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(
      135deg, transparent, transparent 6px, var(--line) 6px, var(--line) 7px
    );
    pointer-events: none;
    z-index: 1;
  }

  .controller-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-3);
  }

  .controller-name {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    font-family: var(--font-sans);
    font-size: var(--t-13);
    color: var(--ink-1);
  }

  .controller-seen {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
  }

  .scenario-chip {
    display: flex;
    align-items: center;
    gap: var(--s-1);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .scenario-icon { font-size: var(--t-14); }

  /* ── Port grid ──────────────────────────────────────────────────────────── */
  .port-grid {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .port-row {
    display: flex;
    align-items: center;
    gap: var(--s-3);
  }

  .port-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    min-width: 56px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .speed-bar-track {
    flex: 1;
    height: 6px;
    background: var(--line);
    border-radius: var(--r-pill);
    overflow: hidden;
  }

  .speed-bar-fill {
    height: 100%;
    background: var(--ink-4);
    border-radius: var(--r-pill);
    transition: width 0.3s ease;
  }

  .speed-bar-fill.active {
    background: var(--accent);
  }

  .speed-value {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    min-width: 36px;
    text-align: right;
  }

  .speed-max {
    font-size: var(--t-9);
    color: var(--ink-4);
  }

  /* ── Chart ──────────────────────────────────────────────────────────────── */
  .chart-wrap {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    padding-top: var(--s-2);
    border-top: 1px solid var(--line);
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

  .offline-note {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    padding-top: var(--s-2);
    border-top: 1px solid var(--line);
  }

  /* ── Override section ───────────────────────────────────────────────────── */
  .override-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
  }

  .override-active {
    display: flex;
    align-items: center;
    justify-content: space-between;
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--st-warn);
  }

  .override-form {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .override-row {
    display: flex;
    align-items: center;
    gap: var(--s-3);
  }

  .override-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    min-width: 64px;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .override-slider {
    flex: 1;
    -webkit-appearance: none;
    appearance: none;
    height: 4px;
    background: var(--line);
    border-radius: var(--r-pill);
    outline: none;
    cursor: pointer;
  }

  .override-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg-0);
    cursor: pointer;
  }

  .override-val {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    min-width: 24px;
    text-align: right;
  }

  .override-select {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    background: var(--bg-0);
    color: var(--ink-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-1) var(--s-3);
  }

  .btn-override, .btn-clear {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: var(--s-2) var(--s-4);
    border-radius: var(--r-2);
    border: 1px solid var(--line);
    cursor: pointer;
    transition: background 0.15s;
    align-self: flex-start;
  }

  .btn-override {
    background: var(--accent);
    color: var(--bg-0);
    border-color: var(--accent);
  }

  .btn-override:hover { opacity: 0.85; }

  .btn-clear {
    background: transparent;
    color: var(--st-warn);
    border-color: var(--st-warn);
  }

  .btn-clear:hover {
    background: var(--st-warn);
    color: var(--bg-0);
  }

  /* ── Loading / empty ────────────────────────────────────────────────────── */
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

  @keyframes slide { to { left: 100%; } }

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
