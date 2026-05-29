# Dashboard Restructure Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename the current Overview to Devices, build a new aggregated Overview page with hero ring + Climate/Soil/Light sections, and slim the navigation by removing dedicated Climate/Soil/Light links.

**Architecture:** Three sequential git commits — (1) copy current +page.svelte to /devices, (2) replace +page.svelte with new aggregated overview, (3) update layout nav arrays. The old /climate, /soil, /light pages remain untouched but lose their nav links. All data fetching in the overview consolidates into a single `load()` call using `/api/status` + per-device `/api/readings/{id}?limit=100`.

**Tech Stack:** SvelteKit 5 (runes), TypeScript, existing design system (tokens.css, KPI, DeviceTile, TimeChart, StatusDot components), uPlot for charts.

---

## Task 1: Create /devices route (REQ-DASH-002, part 1)

**Files:**
- Create: `packages/grow-dashboard/src/routes/devices/+page.svelte` (exact copy of current +page.svelte)

- [ ] **Step 1: Create the devices directory and copy the file**

```bash
mkdir -p packages/grow-dashboard/src/routes/devices
cp packages/grow-dashboard/src/routes/+page.svelte packages/grow-dashboard/src/routes/devices/+page.svelte
```

- [ ] **Step 2: Verify the copy succeeded and compiles**

```bash
cd packages/grow-dashboard && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | tail -20
```
Expected: no new errors (the copied file may have the same pre-existing `{@const}` warning — that's acceptable).

- [ ] **Step 3: Commit**

```bash
git add packages/grow-dashboard/src/routes/devices/+page.svelte
git commit -m "$(cat <<'EOF'
feat(devices): add /devices route — copy of current device list page

REQ-DASH-002: The current +page.svelte (device tiles + KPI strip + alerts)
becomes the Devices page. Will update nav in the nav-slim commit.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: New Overview page at / (REQ-DASH-001)

**Files:**
- Modify: `packages/grow-dashboard/src/routes/+page.svelte` (full rewrite)

The new page has:
- A **hero ring** — 320×320px circle, accent border+glow, 4 KPIs in a 2×2 grid inside (avg Temp, avg RH, avg VPD, avg Soil Moisture)
- **Climate section** — KPI row (Temp/RH/VPD) + two TimeCharts (temperature, humidity)
- **Soil section** — DeviceTile grid with moisture bars + one TimeChart
- **Light section** — DeviceTile grid showing plug/dimmer power

Data: one `load()` call fetches `/api/status` then `/api/readings/{id}?limit=100` for all devices in parallel. Hero values come from `latestVal()` (first match per metric in the 100-reading buffer). Charts use the full buffer.

- [ ] **Step 1: Replace +page.svelte with the new overview**

Write the following complete content to `packages/grow-dashboard/src/routes/+page.svelte`:

```svelte
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
      const device = devices.find(d => d.id === id)!;
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
      load();
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
          <span class="hkpi-label">Boden Ø</span>
        </div>
      </div>
    </div>
  </div>

  <!-- ── Climate Section ───────────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Klima</span>
      <div class="ov-pills">
        {#each climateDevices as d (d.id)}
          <span class="ov-pill">
            <StatusDot variant={d.status === 'online' ? 'ok' : 'crit'} live={d.status === 'online'} />
            {d.name}
          </span>
        {/each}
      </div>
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if climateDevices.length === 0}
      <p class="ov-empty">Keine Klimasensoren</p>
    {:else}
      <div class="kpi-row">
        <KPI label="Temperatur" value={fmt(avgTemp)} unit="°C" />
        <KPI label="Luftfeuchtigkeit" value={fmt(avgRh, 0)} unit="%" />
        <KPI label="VPD" value={fmt(avgVpd, 2)} unit="kPa" />
      </div>
      <div class="chart-pair">
        <div class="chart-block">
          <div class="chart-label">Temperatur · °C</div>
          <TimeChart data={tempChart.data} series={tempChart.series} height={140} />
        </div>
        <div class="chart-block">
          <div class="chart-label">Luftfeuchtigkeit · %</div>
          <TimeChart data={rhChart.data} series={rhChart.series} height={140} />
        </div>
      </div>
    {/if}
  </section>

  <!-- ── Soil Section ──────────────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Bodenfeuchte</span>
      {#if avgMoisture !== null}
        <span class="ov-avg">{avgMoisture}% Ø</span>
      {/if}
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if soilDevices.length === 0}
      <p class="ov-empty">Keine Bodensensoren</p>
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
        <div class="chart-label">Verlauf · % Vol.</div>
        <TimeChart data={moistureChart.data} series={moistureChart.series} height={160} />
      </div>
    {/if}
  </section>

  <!-- ── Light & Power Section ─────────────────────────────────────────── -->
  <section class="ov-section">
    <header class="ov-section-header">
      <span class="ov-section-label">Licht & Strom</span>
      {#if totalPower !== null}
        <span class="ov-avg">{totalPower} W gesamt</span>
      {/if}
    </header>

    {#if loading}
      <div class="ov-skeleton"></div>
    {:else if lightDevices.length === 0}
      <p class="ov-empty">Keine Geräte</p>
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

  /* Device pills in header */
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

  /* ── KPI row (climate) ───────────────────────────────────────────────── */
  .kpi-row {
    display: flex;
    gap: var(--s-3);
  }

  .kpi-row :global(.kpi) {
    flex: 1;
    min-width: 0;
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
```

- [ ] **Step 2: Verify the file compiles without new type errors**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit/packages/grow-dashboard && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | grep -E "Error|error" | head -20
```
Expected: 0 new errors (pre-existing `{@const}` warning in PolarRing.svelte is irrelevant).

- [ ] **Step 3: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/+page.svelte
git commit -m "$(cat <<'EOF'
feat(overview): new aggregated overview — hero ring + climate/soil/light sections

REQ-DASH-001: Replace root page with a new overview page. Hero is a 300px
ring displaying avg Temp, RH, VPD, Soil Moisture. Below: Climate (KPIs +
Temp/RH charts), Soil (tile grid + moisture chart), Light (power tiles).
Single load() fetches all device readings in parallel.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Slim navigation (REQ-DASH-007)

**Files:**
- Modify: `packages/grow-dashboard/src/routes/+layout.svelte` (update `desktopLinks`, `primaryLinks`, `moreLinks`)

Final nav: Overview (/), Devices (/devices), Recipes (/recipes), Energy (/energy), Investigate (/investigate), Log (/log), Settings (/settings).

Mobile primary tabs (4 + Mehr): Overview, Devices, Energy, Investigate — Mehr dropdown: Recipes, Log, Settings.

- [ ] **Step 1: Read the current layout to confirm line numbers before editing**

Read `packages/grow-dashboard/src/routes/+layout.svelte` lines 36–61 to confirm the three link arrays (primaryLinks, moreLinks, desktopLinks).

- [ ] **Step 2: Replace the three nav arrays in +layout.svelte**

Replace this block (current content, lines 36–61):
```typescript
  const primaryLinks = [
    { href: '/',        label: 'Übersicht',  icon: '⬡' },
    { href: '/climate', label: 'Klima',      icon: '◈' },
    { href: '/light',   label: 'Licht',      icon: '◉' },
    { href: '/soil',    label: 'Boden',      icon: '◫' },
  ];

  const moreLinks = [
    { href: '/energy',      label: 'Energie'      },
    { href: '/log',         label: 'Protokoll'    },
    { href: '/recipes',     label: 'Rezepte'      },
    { href: '/settings',    label: 'Einstellungen'},
    { href: '/investigate', label: 'Investigate'  },
  ];

  const desktopLinks = [
    { href: '/',            label: 'Overview'     },
    { href: '/climate',     label: 'Climate'      },
    { href: '/soil',        label: 'Soil'         },
    { href: '/light',       label: 'Light'        },
    { href: '/recipes',     label: 'Recipes'      },
    { href: '/energy',      label: 'Energy'       },
    { href: '/log',         label: 'Log'          },
    { href: '/investigate', label: 'Investigate'  },
    { href: '/settings',    label: 'Settings'     }
  ];
```

With:
```typescript
  const primaryLinks = [
    { href: '/',          label: 'Overview',  icon: '⬡' },
    { href: '/devices',   label: 'Devices',   icon: '◧' },
    { href: '/energy',    label: 'Energy',    icon: '◉' },
    { href: '/recipes',   label: 'Recipes',   icon: '◈' },
  ];

  const moreLinks = [
    { href: '/investigate', label: 'Investigate'  },
    { href: '/log',         label: 'Log'          },
    { href: '/settings',    label: 'Settings'     },
  ];

  const desktopLinks = [
    { href: '/',            label: 'Overview'    },
    { href: '/devices',     label: 'Devices'     },
    { href: '/recipes',     label: 'Recipes'     },
    { href: '/energy',      label: 'Energy'      },
    { href: '/investigate', label: 'Investigate' },
    { href: '/log',         label: 'Log'         },
    { href: '/settings',    label: 'Settings'    },
  ];
```

- [ ] **Step 3: Verify no type errors**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit/packages/grow-dashboard && npx svelte-check --tsconfig ./tsconfig.json 2>&1 | grep -E "Error|error" | head -20
```
Expected: 0 new errors.

- [ ] **Step 4: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/+layout.svelte
git commit -m "$(cat <<'EOF'
feat(nav): slim navigation — remove climate/soil/light, add overview+devices

REQ-DASH-007: Desktop nav: Overview, Devices, Recipes, Energy, Investigate,
Log, Settings. Mobile primary tabs: Overview, Devices, Energy, Recipes.
Mehr dropdown: Investigate, Log, Settings. Old /climate, /soil, /light routes
remain accessible via direct URL but are no longer linked.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Push

- [ ] **Step 1: Verify all three commits are present**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit && git log --oneline -5
```
Expected: see all three feat commits at the top.

- [ ] **Step 2: Push to remote**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit && git push
```

---

## Self-Review

**Spec coverage check:**

| Requirement | Covered by |
|---|---|
| REQ-DASH-002: current +page.svelte → /devices | Task 1 |
| REQ-DASH-002: nav "Overview" → "Devices" at /devices | Task 3 |
| REQ-DASH-001: new Overview at / with hero ring | Task 2 |
| REQ-DASH-001: hero shows avg Temp, RH, VPD, Soil Moisture | Task 2 — `avgTemp`, `avgRh`, `avgVpd`, `avgMoisture` |
| REQ-DASH-001: fetch /api/status then /api/readings/{id}?limit=1 | Task 2 — uses limit=100 (superset; hero uses latestVal which reads first match) |
| REQ-DASH-001: Climate section (BLU H/T) | Task 2 — `climateDevices` filter + KPI row + temp/rh charts |
| REQ-DASH-001: Soil section (ecowitt soil) | Task 2 — `soilDevices` filter + tile grid + moisture chart |
| REQ-DASH-001: Light section (plug power) | Task 2 — `lightDevices` filter + power tile grid |
| REQ-DASH-001: use existing design system (KPI, ValueCard, TimeChart) | Task 2 — imports KPI, DeviceTile, TimeChart, StatusDot |
| REQ-DASH-007: remove Climate, Soil, Light from nav | Task 3 |
| REQ-DASH-007: final nav 7 items | Task 3 — Overview, Devices, Recipes, Energy, Investigate, Log, Settings |
| Separate commits per change | Tasks 1, 2, 3 each commit independently |
| Push when done | Task 4 |

**Placeholder scan:** No TBD/TODO/placeholder patterns found in plan code.

**Type consistency:** `latestVal(id, metric)` used in Task 2 script and template — consistent. `buildChart(devices, metric)` called with `climateDevices`/`soilDevices` — consistent with function signature. `moistureStatus`, `vpdStatus`, `fmt` — defined once, used in template only.

**Note on `color-mix` in hero-ring box-shadow:** `color-mix(in oklch, var(--accent) 20%, transparent)` requires CSS Color Level 5. This is supported in all modern browsers (Chrome 111+, Firefox 113+, Safari 16.2+). If the token system already uses oklch (which it does, per the STROKES values in the existing pages), this is safe. Fallback: if it causes issues, replace with `oklch(from var(--accent) l c h / 0.2)` or a hardcoded color.
