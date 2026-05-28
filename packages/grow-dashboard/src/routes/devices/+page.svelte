<script lang="ts">
  import { get, put, post } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type {
    StatusResponse,
    Device,
    AlertsResponse,
    Alert,
    DayPlanResponse,
    RecipeData,
    ReadingsResponse
  } from '$lib/types.js';
  import { onMount } from 'svelte';
  import KPI from '$lib/components/KPI.svelte';
  import DeviceTile from '$lib/components/DeviceTile.svelte';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';

  // ── State ──────────────────────────────────────────────────────────────────
  let devices = $state<Device[]>([]);
  let alerts = $state<Alert[]>([]);
  let recipe = $state<RecipeData | null>(null);
  let nowMin = $state(getNowMin());
  let sensorData = $state<Record<string, Record<string, number>>>({});

  // Inline device-name editing
  let editingId = $state<string | null>(null);
  let editValue = $state('');

  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }

  // ── KPI derivations ────────────────────────────────────────────────────────
  let temp = $derived(
    sensorData['blu-01']?.temperature ?? sensorData['blu-02']?.temperature ?? null
  );
  let rh = $derived(
    sensorData['blu-01']?.humidity ?? sensorData['blu-02']?.humidity ?? null
  );
  let vpd = $derived(
    sensorData['blu-01']?.vpd ?? sensorData['blu-02']?.vpd ?? null
  );

  let avgMoisture = $derived.by(() => {
    const vals = Array.from({ length: 8 }, (_, i) => sensorData[`soil-0${i + 1}`]?.soil_moisture)
      .filter((v): v is number => v !== undefined);
    if (!vals.length) return null;
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  });

  let totalWatts = $derived.by(() => {
    const sum = ['plug-01', 'plug-02', 'plug-03', 'plug-04', 'plug-05'].reduce(
      (acc, id) => acc + (sensorData[id]?.power ?? 0),
      0
    );
    return sum > 0 ? sum.toFixed(0) : '—';
  });

  let openAlerts = $derived(alerts.filter(a => a.resolved_at === null).length);

  const STALE_MS = 10 * 60_000;
  let climateStale = $derived.by(() => {
    const bluDevices = devices.filter(d => d.device_type === 'blu_ht');
    if (!bluDevices.length) return false;
    return bluDevices.every(d => Date.now() - new Date(d.last_seen).getTime() > STALE_MS);
  });

  let photoStatus = $derived.by(() => {
    if (!recipe) return '—';
    const [onH, onM] = recipe.photoperiod.on.split(':').map(Number);
    const [offH, offM] = recipe.photoperiod.off.split(':').map(Number);
    const onMins = onH * 60 + onM;
    let offMins = offH * 60 + offM;
    if (offMins <= onMins) offMins += 1440;
    const nm = nowMin < onMins ? nowMin + 1440 : nowMin;
    return nm >= onMins && nm < offMins ? 'ON' : 'OFF';
  });

  let photoLabel = $derived(recipe ? `${recipe.photoperiod.on}–${recipe.photoperiod.off}` : '');

  // ── Device grouping ────────────────────────────────────────────────────────
  const GROUP_ORDER = ['Lighting', 'Climate', 'Soil moisture', 'Power', 'Irrigation'] as const;
  type Group = (typeof GROUP_ORDER)[number];

  function deviceGroup(d: Device): Group {
    const n = d.name.toLowerCase();
    const t = d.device_type;
    if (t === 'shelly_dimmer') return 'Lighting';
    if (t === 'shelly_plug') {
      if (n.includes('light') || n.includes('far') || n.includes('dawn') || n.includes('red')) {
        return 'Lighting';
      }
      return 'Power';
    }
    if (t === 'blu_ht' || t === 'ecowitt_indoor') return 'Climate';
    if (t === 'ecowitt_sensor') return 'Soil moisture';
    if (t === 'shelly_relay') return 'Irrigation';
    return 'Power';
  }

  let grouped = $derived.by(() => {
    const map = new Map<Group, Device[]>(GROUP_ORDER.map(g => [g, [] as Device[]]));
    for (const d of devices) {
      const g = deviceGroup(d);
      map.get(g)?.push(d);
    }
    return map;
  });

  let mainLightId = $derived(
    devices.find(
      d =>
        d.device_type === 'shelly_dimmer' ||
        (d.device_type === 'shelly_plug' && d.name.toLowerCase().includes('main light'))
    )?.id ?? null
  );

  // ── Tile helpers ───────────────────────────────────────────────────────────
  function tileMetric(d: Device): { metric: string; unit: string } {
    const s = sensorData[d.id];
    switch (d.device_type) {
      case 'shelly_plug':
      case 'shelly_dimmer':
        return { metric: s?.power != null ? s.power.toFixed(0) : '—', unit: 'W' };
      case 'blu_ht':
        return { metric: s?.temperature != null ? s.temperature.toFixed(1) : '—', unit: '°C' };
      case 'ecowitt_sensor':
        return { metric: s?.soil_moisture != null ? String(Math.round(s.soil_moisture)) : '—', unit: '%' };
      case 'ecowitt_indoor':
        return { metric: s?.temperature != null ? s.temperature.toFixed(1) : '—', unit: '°C' };
      case 'shelly_relay':
        return { metric: d.status === 'online' ? 'RDY' : 'OFF', unit: '' };
      default:
        return { metric: '—', unit: '' };
    }
  }

  function tileStatus(d: Device): 'ok' | 'warn' | 'crit' | 'offline' {
    return d.status === 'online' ? 'ok' : 'offline';
  }

  // ── Alert helpers ──────────────────────────────────────────────────────────
  function alertTone(tier: Alert['tier']): 'crit' | 'warn' | 'info' {
    return tier === 'critical' ? 'crit' : tier === 'warning' ? 'warn' : 'info';
  }

  function relTime(ts: string): string {
    const m = Math.floor((Date.now() - new Date(ts).getTime()) / 60_000);
    if (m < 60) return `${m}m`;
    const h = Math.floor(m / 60);
    return h < 24 ? `${h}h` : `${Math.floor(h / 24)}d`;
  }

  // ── Inline name editing ────────────────────────────────────────────────────
  function startEdit(d: Device) {
    editingId = d.id;
    editValue = d.name;
  }

  function cancelEdit() {
    editingId = null;
    editValue = '';
  }

  async function saveEdit(d: Device) {
    const trimmed = editValue.trim();
    if (!trimmed) { cancelEdit(); return; }
    try {
      await put<Device>(`/api/device/${d.id}/name`, { name: trimmed });
      devices = devices.map(dev => dev.id === d.id ? { ...dev, name: trimmed } : dev);
      editingId = null;
    } catch { /* keep edit open so user can retry */ }
  }

  // ── Device control ─────────────────────────────────────────────────────────
  function isControllable(d: Device): boolean {
    return d.device_type === 'shelly_plug' || d.device_type === 'shelly_relay';
  }

  function switchState(d: Device): boolean | null {
    const v = sensorData[d.id]?.output;
    return v != null ? v > 0 : null;
  }

  async function handleToggle(d: Device) {
    const current = switchState(d);
    const next = current == null ? true : !current;
    if (!window.confirm(`Turn ${d.name} ${next ? 'ON' : 'OFF'}?`)) return;
    try {
      await post(`/api/device/${d.id}/command`, {
        method: 'Switch.Set',
        params: { id: 0, on: next }
      });
      sensorData = { ...sensorData, [d.id]: { ...(sensorData[d.id] ?? {}), output: next ? 1 : 0 } };
    } catch { /* ignore, real state will sync on next poll */ }
  }

  // ── Alert actions ──────────────────────────────────────────────────────────
  async function dismissAlert(id: string) {
    try {
      await post(`/api/alerts/${id}/resolve`, {});
      alerts = alerts.filter(a => a.id !== id);
    } catch { /* ignore */ }
  }

  async function clearAllAlerts() {
    try {
      await post('/api/alerts/resolve-all', {});
      alerts = alerts.filter(a => a.resolved_at !== null);
    } catch { /* ignore */ }
  }

  // ── Data loading ───────────────────────────────────────────────────────────
  async function loadSensors() {
    const ids = [
      'blu-01', 'blu-02',
      'soil-01', 'soil-02', 'soil-03', 'soil-04', 'soil-05', 'soil-06', 'soil-07', 'soil-08',
      'plug-01', 'plug-02', 'plug-03', 'plug-04', 'plug-05'
    ];
    await Promise.allSettled(
      ids.map(async id => {
        try {
          const res = await get<ReadingsResponse>(`/api/readings/${id}?limit=5`);
          if (res.readings?.length) {
            const latest: Record<string, number> = {};
            for (const r of res.readings) {
              if (!(r.metric in latest)) latest[r.metric] = r.value;
            }
            sensorData = { ...sensorData, [id]: latest };
          }
        } catch { /* device has no readings yet */ }
      })
    );
  }

  async function load() {
    try {
      const [statusRes, alertsRes] = await Promise.all([
        get<StatusResponse>('/api/status'),
        get<AlertsResponse>('/api/alerts')
      ]);
      devices = statusRes.devices;
      alerts = alertsRes.alerts;
    } catch { /* ignore */ }

    try {
      const plan = await get<DayPlanResponse>('/api/schedule/today');
      if (plan.recipe_name) {
        recipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(plan.recipe_name)}`);
      }
    } catch { /* no active recipe */ }

    await loadSensors();
  }

  onMount(() => {
    load();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'device_status' || evt?.type === 'sensor_update') {
      load();
    }
  });
</script>

<div class="page">

  <!-- ── Hero KPI Strip ─────────────────────────────────────────────────── -->
  <div class="kpi-strip">
    <!-- Composite Klima (1.4fr) -->
    <div class="kpi-klima-wrapper" class:stale={climateStale}>
      <KPI label="Temp" value={temp != null ? temp.toFixed(1) : '—'} unit="°C" />
      <div class="kpi-divider"></div>
      <KPI label="RH" value={rh != null ? rh.toFixed(0) : '—'} unit="%" />
      <div class="kpi-divider"></div>
      <KPI label="VPD" value={vpd != null ? vpd.toFixed(2) : '—'} unit="kPa" />
    </div>

    <KPI label="Soil moisture" value={avgMoisture ?? '—'} unit="%" />
    <KPI label="Light" value={photoStatus} unit={photoLabel} />
    <KPI label="Energy" value={totalWatts} unit="W" />
    <KPI label="Alerts" value={openAlerts} unit="open" />
  </div>

  <!-- ── Main 2-column layout ───────────────────────────────────────────── -->
  <div class="main-layout">

    <!-- Device tiles -->
    <div class="devices-panel">
      {#each GROUP_ORDER as group}
        {@const groupDevices = grouped.get(group) ?? []}
        {#if groupDevices.length > 0}
          <section class="device-group">
            <h2 class="group-header">{group}</h2>
            <div class="tiles-grid">
              {#each groupDevices as d (d.id)}
                {@const { metric, unit } = tileMetric(d)}
                <div class="tile-wrap" class:main-tile={d.id === mainLightId}>
                  {#if editingId === d.id}
                    <input
                      class="name-input"
                      bind:value={editValue}
                      autofocus
                      onkeydown={(e) => {
                        if (e.key === 'Enter') saveEdit(d);
                        else if (e.key === 'Escape') cancelEdit();
                      }}
                    />
                  {:else}
                    <button class="edit-btn" onclick={() => startEdit(d)} title="Rename device"
                      >✎</button
                    >
                  {/if}
                  <DeviceTile
                    label={editingId === d.id ? editValue : d.name}
                    sub={d.zone}
                    {metric}
                    {unit}
                    status={tileStatus(d)}
                    lastSeen={d.last_seen}
                    periodic={d.device_type === 'blu_ht'}
                    toggled={isControllable(d) ? switchState(d) : null}
                    onToggle={isControllable(d) ? () => handleToggle(d) : undefined}
                  />
                </div>
              {/each}
            </div>
          </section>
        {/if}
      {/each}
    </div>

    <!-- Sidebar: PolarRing + Alerts -->
    <aside class="sidebar">
      {#if recipe}
        <div class="sidebar-panel recipe-panel">
          <div class="group-header">{recipe.name}</div>
          <div class="polar-center">
            <PolarRing {recipe} {nowMin} size="md" />
          </div>
        </div>
      {/if}

      <div class="sidebar-panel alerts-panel">
        <div class="alerts-header">
          <span class="group-header">Alerts</span>
          <div class="alerts-header-right">
            {#if openAlerts > 0}
              <span class="alert-badge">{openAlerts}</span>
              <button class="clear-all-btn" onclick={clearAllAlerts}>Clear all</button>
            {/if}
          </div>
        </div>

        {#if alerts.filter(a => a.resolved_at === null).length === 0}
          <p class="empty-state">No alerts</p>
        {:else}
          <ul class="alert-list">
            {#each alerts.filter(a => a.resolved_at === null) as a (a.id)}
              <li class="alert-item">
                <StatusDot variant={alertTone(a.tier)} live={true} />
                <div class="alert-body">
                  <span class="alert-msg">{a.message}</span>
                  <span class="alert-meta">{a.source} · {relTime(a.timestamp)}</span>
                </div>
                <button class="dismiss-btn" onclick={() => dismissAlert(a.id)} aria-label="Dismiss alert">✕</button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    </aside>

  </div>
</div>

<style>
  /* ── Page shell ─────────────────────────────────────────────────────────── */
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  /* ── KPI Strip ──────────────────────────────────────────────────────────── */
  .kpi-strip {
    display: grid;
    grid-template-columns: 1.4fr 1fr 1fr 1fr 1fr;
    gap: var(--s-4);
    align-items: stretch;
  }

  /* Composite Klima wrapper: merges three KPI components into one panel */
  .kpi-klima-wrapper {
    display: flex;
    align-items: stretch;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
  }

  /* Strip individual borders/backgrounds from nested KPI components */
  .kpi-klima-wrapper :global(.kpi) {
    flex: 1;
    border: none;
    border-radius: 0;
    background: transparent;
    min-width: 0;
  }

  .kpi-klima-wrapper.stale :global(.kpi-value),
  .kpi-klima-wrapper.stale :global(.kpi-unit) {
    color: var(--ink-4);
    opacity: 0.6;
  }

  .kpi-divider {
    width: 1px;
    background: var(--line);
    align-self: stretch;
    flex-shrink: 0;
  }

  /* ── Main layout ─────────────────────────────────────────────────────────── */
  .main-layout {
    display: grid;
    grid-template-columns: 1fr 300px;
    gap: var(--s-4);
    align-items: start;
  }

  /* ── Devices panel ───────────────────────────────────────────────────────── */
  .devices-panel {
    display: flex;
    flex-direction: column;
    gap: var(--s-6);
  }

  .device-group {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .group-header {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    font-weight: 400;
    margin: 0;
    padding: 0;
    line-height: 1.4;
  }

  .tiles-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
    gap: var(--s-4);
  }

  /* Main light tile spans 2 columns */
  .main-tile {
    grid-column: span 2;
  }

  /* ── Tile name editing ──────────────────────────────────────────────────── */
  .tile-wrap {
    position: relative;
  }

  .edit-btn {
    position: absolute;
    top: var(--s-2);
    right: var(--s-2);
    z-index: 2;
    background: none;
    border: none;
    cursor: pointer;
    color: var(--ink-4);
    font-size: var(--t-11);
    padding: 2px 4px;
    border-radius: var(--r-1);
    line-height: 1;
    opacity: 0;
    transition: opacity 0.1s;
  }

  .tile-wrap:hover .edit-btn {
    opacity: 1;
  }

  .name-input {
    position: absolute;
    top: var(--s-2);
    left: var(--s-3);
    right: var(--s-3);
    z-index: 2;
    background: var(--bg-0);
    border: 1px solid var(--accent);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font-family: var(--font-sans);
    font-size: var(--t-12);
    padding: 2px var(--s-2);
    outline: none;
  }

  /* ── Sidebar ─────────────────────────────────────────────────────────────── */
  .sidebar {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    position: sticky;
    top: var(--s-4);
  }

  .sidebar-panel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .polar-center {
    display: flex;
    justify-content: center;
    align-items: center;
    padding: var(--s-2) 0;
  }

  /* ── Alerts ──────────────────────────────────────────────────────────────── */
  .alerts-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .alerts-header-right {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .alert-badge {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    background: var(--st-crit-soft);
    color: var(--st-crit);
    padding: 1px 6px;
    border-radius: var(--r-pill);
    font-variant-numeric: tabular-nums;
    line-height: 1.6;
  }

  .clear-all-btn {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 1px 6px;
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.6;
  }

  .clear-all-btn:hover {
    color: var(--ink-1);
    border-color: var(--ink-3);
  }

  .dismiss-btn {
    flex-shrink: 0;
    margin-left: auto;
    background: none;
    border: none;
    color: var(--ink-4);
    cursor: pointer;
    font-size: var(--t-10);
    padding: 0 0 0 var(--s-2);
    line-height: 1;
    align-self: center;
  }

  .dismiss-btn:hover {
    color: var(--ink-1);
  }

  .alert-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .alert-item {
    display: flex;
    align-items: flex-start;
    gap: var(--s-2);
    padding: var(--s-2) 0;
    border-bottom: 1px solid var(--line);
  }

  .alert-item:last-child {
    border-bottom: none;
    padding-bottom: 0;
  }

  .alert-item.resolved {
    opacity: 0.4;
  }

  .alert-body {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .alert-msg {
    font-size: var(--t-11);
    color: var(--ink-1);
    line-height: 1.4;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
  }

  .alert-meta {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .empty-state {
    font-size: var(--t-11);
    color: var(--ink-4);
    margin: 0;
    text-align: center;
    padding: var(--s-4) 0;
  }
</style>
