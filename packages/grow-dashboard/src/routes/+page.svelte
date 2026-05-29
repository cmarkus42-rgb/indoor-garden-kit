<script lang="ts">
  import { get } from '$lib/api.js';
  import { visibleDevices } from '$lib/visibility.js';
  import { sseLatest } from '$lib/sse.js';
  import type {
    StatusResponse, ReadingsResponse, Device, SensorReading,
    DayPlanResponse, RecipeData
  } from '$lib/types.js';
  import { onMount } from 'svelte';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import KPI from '$lib/components/KPI.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import TimeChart from '$lib/components/TimeChart.svelte';
  import DeviceTile from '$lib/components/DeviceTile.svelte';
  import type uPlot from 'uplot';
  import TimeRangeSlider, { filterByRange, LOG_STEPS } from '$lib/components/TimeRangeSlider.svelte';

  // ── Section config ─────────────────────────────────────────────────────────
  const SECTION_KEYS = ["climate", "soil", "light"] as const;
  type SectionKey = typeof SECTION_KEYS[number];
  interface OverviewConfig { order: SectionKey[]; visible: Record<SectionKey, boolean>; }
  const DEFAULT_CONFIG: OverviewConfig = {
    order: ["climate", "soil", "light"],
    visible: { climate: true, soil: true, light: true }
  };
  const STORAGE_KEY = "grow_overview_config";

  const SECTION_LABELS: Record<SectionKey, string> = {
    climate: "Climate",
    soil: "Soil Moisture",
    light: "Light"
  };

  function loadConfig(): OverviewConfig {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw) as OverviewConfig;
        if (Array.isArray(parsed.order) && parsed.visible) return parsed;
      }
    } catch {}
    return {
      order: [...DEFAULT_CONFIG.order],
      visible: { ...DEFAULT_CONFIG.visible }
    };
  }

  function saveConfig() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
  }

  // ── Edit mode ──────────────────────────────────────────────────────────────
  let editMode = $state(false);
  let config = $state<OverviewConfig>(loadConfig());
  let draggedKey = $state<SectionKey | null>(null);
  let draggedOver = $state<SectionKey | null>(null);

  function toggleEdit() {
    if (editMode) saveConfig();
    editMode = !editMode;
  }

  function onDragStart(e: DragEvent, key: SectionKey) {
    draggedKey = key;
    e.dataTransfer!.setData("text/plain", key);
    e.dataTransfer!.effectAllowed = "move";
  }

  function onDragOver(e: DragEvent, key: SectionKey) {
    e.preventDefault();
    draggedOver = key;
  }

  function onDrop(e: DragEvent, targetKey: SectionKey) {
    e.preventDefault();
    if (!draggedKey || draggedKey === targetKey) {
      draggedKey = null; draggedOver = null; return;
    }
    const srcIdx = config.order.indexOf(draggedKey);
    const tgtIdx = config.order.indexOf(targetKey);
    const newOrder = [...config.order];
    newOrder.splice(srcIdx, 1);
    newOrder.splice(tgtIdx, 0, draggedKey);
    config.order = newOrder;
    saveConfig();
    draggedKey = null;
    draggedOver = null;
  }

  function onDragEnd() {
    draggedKey = null;
    draggedOver = null;
  }

  function toggleVisibility(key: SectionKey) {
    config.visible = { ...config.visible, [key]: !config.visible[key] };
    saveConfig();
  }

  // ── State ────────────────────────────────────────────────────────────────────
  let climateDevices = $state<Device[]>([]);
  let soilDevices = $state<Device[]>([]);
  let climateReadings = $state<Map<string, SensorReading[]>>(new Map());
  let soilReadings = $state<Map<string, SensorReading[]>>(new Map());
  let dayPlan = $state<DayPlanResponse | null>(null);
  let activeRecipe = $state<RecipeData | null>(null);
  let loading = $state(true);

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
  const FILLS = STROKES.map(s => s.replace(')', ' / 0.12)'));

  // ── Load climate data ──────────────────────────────────────────────────────
  function sinceParam(): string {
    const step = LOG_STEPS[Number(rangeStep)];
    if (!step || step.seconds === Infinity) return '';
    const since = Math.round(Date.now() / 1000) - step.seconds;
    return `&since=${since}`;
  }

  async function loadClimate() {
    const status = await get<StatusResponse>('/api/status');
    const visible = visibleDevices(status.devices, 'overview');
    climateDevices = visible.filter(
      d => d.device_type === 'ac_infinity' || d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor'
    );
    soilDevices = visible.filter(d => d.device_type === 'ecowitt_sensor');

    await loadReadings();
  }

  async function loadReadings() {
    const since = sinceParam();

    const cMap = new Map<string, SensorReading[]>();
    await Promise.all(
      climateDevices.map(async d => {
        const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=5000${since}`);
        cMap.set(d.id, res.readings);
      })
    );
    climateReadings = cMap;

    const sMap = new Map<string, SensorReading[]>();
    await Promise.all(
      soilDevices.map(async d => {
        const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=5000${since}`);
        sMap.set(d.id, res.readings);
      })
    );
    soilReadings = sMap;
  }

  async function loadSchedule() {
    try {
      dayPlan = await get<DayPlanResponse>('/api/schedule/today');
      if (dayPlan?.recipe_name) {
        activeRecipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(dayPlan.recipe_name)}`);
      }
    } catch {
      dayPlan = null;
      activeRecipe = null;
    }
  }

  async function loadAll() {
    loading = true;
    await Promise.all([loadClimate(), loadSchedule()]);
    loading = false;
  }

  onMount(() => {
    loadAll();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'sensor_update' || evt?.type === 'wind_update') loadClimate();
    if (evt?.type === 'schedule_pushed') loadSchedule();
  });

  // ── Now-minute for PolarRing ───────────────────────────────────────────────
  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  let nowMin = $state(getNowMin());

  // ── Time range slider (logarithmic) ──────────────────────────────────────
  let rangeStep = $state(4);  // default: "Last 24 hours" (BUGFIX: was 0 = "Last hour")

  // ── Climate KPI helpers ────────────────────────────────────────────────────
  function latestVal(map: Map<string, SensorReading[]>, devs: Device[], metric: string): number | null {
    for (const d of devs) {
      const r = map.get(d.id)?.find(r => r.metric === metric);
      if (r) return r.value;
    }
    return null;
  }

  let temp = $derived(latestVal(climateReadings, climateDevices, 'temperature'));
  let rh = $derived(latestVal(climateReadings, climateDevices, 'humidity'));
  let vpd = $derived(latestVal(climateReadings, climateDevices, 'vpd'));

  function vpdStatus(v: number | null): 'ok' | 'warn' | 'crit' {
    if (v === null) return 'crit';
    if (v >= 0.8 && v <= 1.6) return 'ok';
    if (v > 1.6 || v < 0.5) return 'crit';
    return 'warn';
  }

  // ── Soil KPI ───────────────────────────────────────────────────────────────
  function soilLatest(id: string): number | null {
    const r = soilReadings.get(id)?.find(r => r.metric === 'soil_moisture');
    return r?.value ?? null;
  }

  let avgMoisture = $derived.by(() => {
    const vals = soilDevices
      .map(d => soilLatest(d.id))
      .filter((v): v is number => v !== null);
    if (!vals.length) return null;
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  });

  let dryBackPct = $derived.by(() => {
    const allVals: number[] = [];
    for (const d of soilDevices) {
      for (const r of soilReadings.get(d.id) ?? []) {
        if (r.metric === "soil_moisture") allVals.push(r.value);
      }
    }
    if (allVals.length < 2) return null;
    const peak = Math.max(...allVals);
    const trough = Math.min(...allVals);
    return Math.round(peak - trough);
  });

  function moistureStatus(v: number | null): 'ok' | 'warn' | 'crit' | 'offline' {
    if (v === null) return 'offline';
    if (v >= 30 && v <= 70) return 'ok';
    if (v < 15 || v > 85) return 'crit';
    return 'warn';
  }

  // ── Climate chart builder ──────────────────────────────────────────────────
  function buildClimateChart(metric: string): { data: uPlot.AlignedData; series: uPlot.Series[] } {
    const allTs = new Set<number>();
    const devMaps: Map<string, Map<number, number>> = new Map();

    for (const d of climateDevices) {
      const m = new Map<number, number>();
      for (const r of climateReadings.get(d.id) ?? []) {
        if (r.metric === metric) {
          const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
          allTs.add(ts);
          m.set(ts, r.value);
        }
      }
      if (m.size) devMaps.set(d.id, m);
    }

    const xs = [...allTs].sort((a, b) => a - b);
    const uSeries: uPlot.Series[] = [{}];
    const ys: (number | null)[][] = [];

    let colorIdx = 0;
    for (const [id, m] of devMaps) {
      const device = climateDevices.find(d => d.id === id)!;
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

    return { data: [xs, ...ys] as uPlot.AlignedData, series: uSeries };
  }

  // Combined climate chart: Temp + RH + VPD on separate y
  let climateChart = $derived.by(() => {
    // Build separate aligned arrays for temp, rh, vpd and merge timestamps
    const allTs = new Set<number>();
    const tempMap = new Map<number, number>();
    const rhMap = new Map<number, number>();
    const vpdMap = new Map<number, number>();

    for (const d of climateDevices) {
      for (const r of climateReadings.get(d.id) ?? []) {
        const ts = Math.round(new Date(r.timestamp).getTime() / 1000);
        allTs.add(ts);
        if (r.metric === 'temperature' && !tempMap.has(ts)) tempMap.set(ts, r.value);
        if (r.metric === 'humidity' && !rhMap.has(ts)) rhMap.set(ts, r.value);
        if (r.metric === 'vpd' && !vpdMap.has(ts)) vpdMap.set(ts, r.value);
      }
    }

    const xs = [...allTs].sort((a, b) => a - b);
    const series: uPlot.Series[] = [
      {},
      { label: 'Temp', stroke: STROKES[0], fill: FILLS[0], width: 1.5, spanGaps: false },
      { label: 'RH',   stroke: STROKES[1], fill: FILLS[1], width: 1.5, spanGaps: false },
      { label: 'VPD',  stroke: STROKES[3], fill: FILLS[3], width: 1.5, spanGaps: false },
    ];
    const data: uPlot.AlignedData = [
      xs,
      xs.map(t => tempMap.get(t) ?? null),
      xs.map(t => rhMap.get(t) ?? null),
      xs.map(t => vpdMap.get(t) ?? null),
    ] as uPlot.AlignedData;

    return { data, series };
  });

  // ── Soil chart ─────────────────────────────────────────────────────────────
  let moistureChart = $derived.by(() => {
    const allTs = new Set<number>();
    const devMaps: { id: string; name: string; m: Map<number, number> }[] = [];

    for (const d of soilDevices) {
      const m = new Map<number, number>();
      for (const r of soilReadings.get(d.id) ?? []) {
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

  // ── Filtered chart data (time range) ──────────────────────────────────────
  // Reload readings when slider changes
  let prevRange = rangeStep;
  $effect(() => {
    const r = rangeStep;
    if (r !== prevRange && climateDevices.length > 0) {
      prevRange = r;
      loadReadings();
    }
  });

  // ── VPD band overlay ───────────────────────────────────────────────────────
  const vpdHooks: uPlot.Hooks.Arrays = {
    draw: [(u) => {
      const ctx = u.ctx;
      ctx.save();
      const dpr = devicePixelRatio || 1;
      const left = u.bbox.left;
      const w = u.bbox.width;

      const vegTop = u.valToPos(1.2, 'y', true);
      const vegBot = u.valToPos(0.8, 'y', true);
      ctx.fillStyle = 'oklch(78% 0.16 145 / 0.13)';
      ctx.fillRect(left, vegTop, w, vegBot - vegTop);

      const flowTop = u.valToPos(1.6, 'y', true);
      const flowBot = u.valToPos(1.2, 'y', true);
      ctx.fillStyle = 'oklch(78% 0.16 75 / 0.13)';
      ctx.fillRect(left, flowTop, w, flowBot - flowTop);

      ctx.font = `${10 * dpr}px JetBrains Mono`;
      ctx.fillStyle = 'oklch(78% 0.16 145 / 0.55)';
      ctx.fillText('VEG', left + 6 * dpr, vegBot - 5 * dpr);
      ctx.fillStyle = 'oklch(78% 0.16 75 / 0.55)';
      ctx.fillText('FLOWER', left + 6 * dpr, flowBot - 5 * dpr);

      ctx.restore();
    }],
  };

  // ── Soil threshold hooks ───────────────────────────────────────────────────
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

      drawLine(30, 'oklch(78% 0.16 75 / 0.7)', '30%');
      drawLine(60, 'oklch(78% 0.16 145 / 0.7)', '60%');

      ctx.restore();
    }],
  };

  // ── Formatting helpers ─────────────────────────────────────────────────────
  function fmt(v: number | null, d = 1): string {
    return v !== null ? v.toFixed(d) : '—';
  }

  function formatLastSeen(iso: string): string {
    const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60_000);
    if (m < 1) return 'just now';
    if (m < 60) return `${m}m ago`;
    const h = Math.floor(m / 60);
    return h < 24 ? `${h}h ago` : `${Math.floor(h / 24)}d ago`;
  }

  function minuteToHHMM(m: number): string {
    const h = Math.floor((m % 1440) / 60);
    const min = (m % 1440) % 60;
    return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
  }
</script>

<div class="page">

  <!-- ══════════════════════════════════════════════════════════════════════════
       EDIT BUTTON
       ══════════════════════════════════════════════════════════════════════════ -->
  <div class="page-topbar">
    <button class="btn-ghost" onclick={toggleEdit}>
      {editMode ? "Done" : "Edit"}
    </button>
  </div>

  <!-- ══════════════════════════════════════════════════════════════════════════
       HERO SECTION: PolarRing + KPI Cards
       ══════════════════════════════════════════════════════════════════════════ -->
  <section class="hero">
    {#if activeRecipe}
      <div class="hero-ring">
        <PolarRing recipe={activeRecipe} {nowMin} size="md" />
      </div>
    {/if}
    <div class="hero-kpis">
      <KPI label="Temperature" value={fmt(temp)} unit="°C" />
      <KPI label="Humidity" value={fmt(rh, 0)} unit="%" />
      <div class="kpi-vpd-wrap">
        <KPI label="VPD" value={fmt(vpd, 2)} unit="kPa" />
        <div class="vpd-badge"><StatusDot variant={vpdStatus(vpd)} /></div>
      </div>
      <KPI label="Soil Avg" value={avgMoisture !== null ? String(avgMoisture) : '—'} unit="%" />
      {#if !activeRecipe}
        <span class="no-schedule-hint">No active schedule</span>
      {/if}
    </div>
  </section>

  <!-- ══════════════════════════════════════════════════════════════════════════
       TIME RANGE SLIDER
       ══════════════════════════════════════════════════════════════════════════ -->
  <TimeRangeSlider bind:value={rangeStep} />

  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading sensor data…</span>
    </div>
  {:else}

    {#each config.order as key (key)}
      {#if editMode || config.visible[key]}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div
          class="section-wrapper"
          class:edit-active={editMode}
          class:drag-over={editMode && draggedOver === key && draggedKey !== key}
          class:dimmed={editMode && !config.visible[key]}
          draggable={editMode}
          role={editMode ? "listitem" : undefined}
          ondragstart={(e) => onDragStart(e, key)}
          ondragover={(e) => onDragOver(e, key)}
          ondrop={(e) => onDrop(e, key)}
          ondragend={onDragEnd}
        >
          {#if editMode}
            <div class="edit-bar">
              <span class="drag-handle" title="Drag to reorder">⠿⠿</span>
              <span class="edit-label">{SECTION_LABELS[key]}</span>
              <label class="vis-toggle" title={config.visible[key] ? "Hide section" : "Show section"}>
                <input
                  type="checkbox"
                  checked={config.visible[key]}
                  onchange={() => toggleVisibility(key)}
                />
                <span class="track"></span>
                <span class="thumb"></span>
              </label>
            </div>
          {/if}

          {#if key === "climate"}
            <!-- ════════════════════════════════════════════════════════════════
                 CLIMATE SECTION
                 ════════════════════════════════════════════════════════════════ -->
            <section class="section">
              <header class="section-header">
                <span class="section-label">Climate</span>
                <span class="section-hint">
                  <span class="band-swatch ok"></span> Veg 0.8–1.2
                  <span class="band-swatch warn"></span> Flower 1.2–1.6
                </span>
              </header>

              {#if climateDevices.length}
                <TimeChart
                  data={climateChart.data}
                  series={climateChart.series}
                  height={160}
                  hooks={vpdHooks}
                />
                <div class="device-row">
                  {#each climateDevices as d}
                    {@const t = latestVal(climateReadings, [d], 'temperature')}
                    {@const h = latestVal(climateReadings, [d], 'humidity')}
                    <DeviceTile
                      label={d.name}
                      sub={`${fmt(h, 0)}% RH`}
                      metric={fmt(t)}
                      unit="°C"
                      status={d.status === 'online' ? 'ok' : 'crit'}
                      periodic={true}
                      lastSeen={d.last_seen}
                    />
                  {/each}
                </div>
              {:else}
                <div class="empty">No climate sensors found</div>
              {/if}
            </section>

          {:else if key === "soil"}
            <!-- ════════════════════════════════════════════════════════════════
                 SOIL MOISTURE SECTION
                 ════════════════════════════════════════════════════════════════ -->
            <section class="section">
              <header class="section-header">
                <span class="section-label">Soil Moisture</span>
                <span class="section-hint">
                  <span class="th-swatch warn"></span> 30% dry
                  <span class="th-swatch ok"></span> 60% field cap.
                </span>
              </header>

              {#if soilDevices.length}
                <TimeChart
                  data={moistureChart.data}
                  series={moistureChart.series}
                  height={160}
                  hooks={thresholdHooks}
                />
                {#if dryBackPct !== null}
                  <div class="dryback-widget">
                    <div class="dryback-header">
                      <span class="section-label">DRY-BACK</span>
                      <span class="dryback-value">{dryBackPct}<span class="dryback-unit">%</span></span>
                      <span class="dryback-quality" class:good={dryBackPct >= 5 && dryBackPct <= 15} class:aggressive={dryBackPct > 15} class:low={dryBackPct < 5}>
                        {dryBackPct < 5 ? "LOW" : dryBackPct <= 15 ? "OPTIMAL" : "AGGRESSIVE"}
                      </span>
                    </div>
                    <div class="dryback-desc">Peak-to-trough VWC swing (last 24h)</div>
                  </div>
                {/if}
                <div class="soil-grid">
                  {#each soilDevices as d, i (d.id)}
                    {@const moisture = soilLatest(d.id)}
                    <div class="soil-cell">
                      <DeviceTile
                        label={d.name}
                        sub={d.zone}
                        metric={fmt(moisture, 0)}
                        unit="%"
                        status={moistureStatus(moisture)}
                        periodic={true}
                        lastSeen={d.last_seen}
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
              {:else}
                <div class="empty">No soil sensors found</div>
              {/if}
            </section>

          {:else if key === "light"}
            <!-- ════════════════════════════════════════════════════════════════
                 LIGHT SECTION (compact)
                 ════════════════════════════════════════════════════════════════ -->
            <section class="section">
              <header class="section-header">
                <span class="section-label">Light</span>
              </header>

              {#if dayPlan && activeRecipe}
                <div class="light-compact">
                  <div class="light-info">
                    <span class="recipe-name">{dayPlan.recipe_name}</span>
                    <div class="photoperiod">
                      <span class="mono-dim">{minuteToHHMM(dayPlan.main_on)}</span>
                      <span class="period-arrow">→</span>
                      <span class="mono-dim">{minuteToHHMM(dayPlan.main_off)}</span>
                    </div>
                    {#if dayPlan.transition_progress !== null}
                      <div class="transition-row">
                        <span class="mono-label-sm">TRANSITION</span>
                        <div class="transition-bar">
                          <div class="transition-fill" style="width: {Math.round(dayPlan.transition_progress * 100)}%"></div>
                        </div>
                        <span class="mono-dim-sm">{Math.round(dayPlan.transition_progress * 100)}%</span>
                      </div>
                    {/if}
                  </div>
                  <div class="light-ring">
                    <PolarRing recipe={activeRecipe} {nowMin} size="sm" />
                  </div>
                </div>
              {:else}
                <div class="empty">No active schedule</div>
              {/if}
            </section>
          {/if}

        </div>
      {/if}
    {/each}

  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-5);
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  /* ── Top bar ────────────────────────────────────────────────────────────────── */
  .page-topbar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: calc(-1 * var(--s-3));
  }

  .btn-ghost {
    background: none;
    border: none;
    padding: var(--s-1) var(--s-3);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    cursor: pointer;
    border-radius: var(--r-1);
    transition: color 0.15s, background 0.15s;
  }

  .btn-ghost:hover {
    color: var(--ink-1);
    background: var(--bg-2);
  }

  /* ── Section wrapper (edit mode) ───────────────────────────────────────────── */
  .section-wrapper {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .section-wrapper.edit-active {
    padding: var(--s-2);
    border: 1px dashed var(--line-strong);
    border-radius: var(--r-2);
    cursor: default;
  }

  .section-wrapper.drag-over {
    border-color: var(--accent);
  }

  .section-wrapper.dimmed {
    opacity: 0.4;
  }

  /* ── Edit bar ───────────────────────────────────────────────────────────────── */
  .edit-bar {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding-bottom: var(--s-2);
  }

  .drag-handle {
    color: var(--ink-4);
    cursor: grab;
    font-size: 16px;
    line-height: 1;
    user-select: none;
    flex-shrink: 0;
  }

  .drag-handle:active {
    cursor: grabbing;
  }

  .edit-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    flex: 1;
  }

  /* ── Visibility toggle ─────────────────────────────────────────────────────── */
  .vis-toggle {
    position: relative;
    display: inline-block;
    width: 32px;
    height: 18px;
    flex-shrink: 0;
    cursor: pointer;
  }

  .vis-toggle input {
    opacity: 0;
    width: 0;
    height: 0;
    position: absolute;
  }

  .vis-toggle .track {
    position: absolute;
    inset: 0;
    background: var(--bg-3);
    border-radius: var(--r-pill);
    transition: background 0.2s;
  }

  .vis-toggle input:checked + .track {
    background: var(--accent);
  }

  .vis-toggle .thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    background: white;
    border-radius: 50%;
    transition: transform 0.2s;
    pointer-events: none;
  }

  .vis-toggle input:checked ~ .thumb {
    transform: translateX(14px);
  }

  /* ── Hero ──────────────────────────────────────────────────────────────────── */
  .hero {
    display: flex;
    align-items: center;
    gap: var(--s-5);
  }

  .hero-ring { flex-shrink: 0; }

  .hero-kpis {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-3);
    flex: 1;
    min-width: 0;
  }

  .hero-kpis :global(.kpi) {
    flex: 1 1 120px;
    min-width: 120px;
  }

  .kpi-vpd-wrap {
    position: relative;
    flex: 1 1 120px;
    min-width: 120px;
  }

  .kpi-vpd-wrap :global(.kpi) {
    flex: unset;
    width: 100%;
  }

  .vpd-badge {
    position: absolute;
    top: var(--s-2);
    right: var(--s-2);
  }

  .no-schedule-hint {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    align-self: center;
    flex-basis: 100%;
  }

  /* ── Sections ──────────────────────────────────────────────────────────────── */
  .section {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .section-header {
    display: flex;
    align-items: baseline;
    gap: var(--s-3);
    padding-bottom: var(--s-2);
    border-bottom: 1px solid var(--line);
  }

  .section-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
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

  .th-swatch {
    display: inline-block;
    width: 14px;
    height: 2px;
    border-radius: 1px;
    flex-shrink: 0;
  }

  .th-swatch.ok   { background: var(--st-ok); }
  .th-swatch.warn { background: var(--st-warn); }

  /* ── Climate device row ────────────────────────────────────────────────────── */
  .device-row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-3);
  }

  .device-row :global(.device-tile) {
    flex: 1 1 200px;
    min-width: 180px;
  }

  /* ── Dry-back widget ──────────────────────────────────────────────────────── */
  .dryback-widget {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-3) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .dryback-header {
    display: flex;
    align-items: baseline;
    gap: var(--s-3);
  }

  .dryback-value {
    font: 600 var(--t-24) var(--font-mono);
    color: var(--ink-1);
    line-height: 1;
  }

  .dryback-unit {
    font-size: var(--t-12);
    color: var(--ink-3);
  }

  .dryback-quality {
    font: 500 var(--t-9) var(--font-mono);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 2px var(--s-2);
    border-radius: var(--r-pill);
  }

  .dryback-quality.good {
    background: var(--st-ok-soft);
    color: var(--st-ok);
  }

  .dryback-quality.aggressive {
    background: var(--st-warn-soft);
    color: var(--st-warn);
  }

  .dryback-quality.low {
    background: var(--st-crit-soft);
    color: var(--st-crit);
  }

  .dryback-desc {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
  }

  /* ── Soil grid 4 columns ───────────────────────────────────────────────────── */
  .soil-grid {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
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

  /* ── Light compact ─────────────────────────────────────────────────────────── */
  .light-compact {
    display: flex;
    align-items: center;
    gap: var(--s-4);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4);
  }

  .light-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .light-ring { flex-shrink: 0; }

  .recipe-name {
    font: 600 var(--t-16) var(--font-sans);
    color: var(--ink-1);
    line-height: 1.2;
  }

  .photoperiod {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .mono-dim {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.04em;
  }

  .period-arrow {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-4);
  }

  .transition-row {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .mono-label-sm {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    flex-shrink: 0;
  }

  .mono-dim-sm {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    flex-shrink: 0;
  }

  .transition-bar {
    flex: 1;
    height: 3px;
    background: var(--bg-3);
    border-radius: var(--r-pill);
    overflow: hidden;
  }

  .transition-fill {
    height: 100%;
    background: var(--accent);
    border-radius: var(--r-pill);
    transition: width 0.4s ease;
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
    padding: var(--s-6) 0;
  }

  /* ── Responsive ────────────────────────────────────────────────────────────── */
  @media (max-width: 768px) {
    .hero {
      flex-direction: column;
      align-items: stretch;
    }

    .hero-ring {
      display: flex;
      justify-content: center;
    }

    .hero-kpis {
      flex-direction: column;
    }

    .hero-kpis :global(.kpi) {
      flex: unset;
      width: 100%;
    }

    .kpi-vpd-wrap {
      flex: unset;
      width: 100%;
    }

    .soil-grid {
      grid-template-columns: repeat(2, 1fr);
    }

    .light-compact {
      flex-direction: column;
      align-items: stretch;
    }

    .light-ring {
      display: flex;
      justify-content: center;
    }
  }
</style>
