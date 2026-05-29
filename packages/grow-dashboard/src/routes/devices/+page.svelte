<script lang="ts">
  import { get, put, post, getGroups, createGroup, updateGroup, deleteGroup } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type {
    StatusResponse,
    Device,
    AlertsResponse,
    Alert,
    DayPlanResponse,
    RecipeData,
    ReadingsResponse,
    DeviceGroup
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

  // ── KPI derivations (dynamic from loaded devices) ──────────────────────────
  let temp = $derived.by(() => {
    const blu = devices.filter(d => d.device_type === 'blu_ht');
    for (const d of blu) {
      const v = sensorData[d.id]?.temperature;
      if (v !== undefined) return v;
    }
    return null;
  });
  let rh = $derived.by(() => {
    const blu = devices.filter(d => d.device_type === 'blu_ht');
    for (const d of blu) {
      const v = sensorData[d.id]?.humidity;
      if (v !== undefined) return v;
    }
    return null;
  });
  let vpd = $derived.by(() => {
    const blu = devices.filter(d => d.device_type === 'blu_ht');
    for (const d of blu) {
      const v = sensorData[d.id]?.vpd;
      if (v !== undefined) return v;
    }
    return null;
  });

  let avgMoisture = $derived.by(() => {
    const vals = devices
      .filter(d => d.device_type === 'ecowitt_sensor')
      .map(d => sensorData[d.id]?.soil_moisture)
      .filter((v): v is number => v !== undefined);
    if (!vals.length) return null;
    return Math.round(vals.reduce((a, b) => a + b, 0) / vals.length);
  });

  let totalWatts = $derived.by(() => {
    const sum = devices
      .filter(d => d.device_type === 'shelly_plug')
      .reduce((acc, d) => acc + (sensorData[d.id]?.power_w ?? 0), 0);
    return sum > 0 ? sum.toFixed(0) : '—';
  });

  let openAlerts = $derived(alerts.filter(a => a.resolved_at === null).length);

  // ── Group management ────────────────────────────────────────────────────────
  let groups = $state<DeviceGroup[]>([]);
  // groupEditId: null = closed, 'new' = creating, <uuid string> = editing existing
  let groupEditId = $state<string | null>(null);
  let groupForm = $state<{ name: string; category: DeviceGroup['category']; device_ids: string[]; color: string }>({
    name: '',
    category: 'light',
    device_ids: [],
    color: '#4ade80'
  });

  const GROUP_COLORS = [
    '#4ade80', '#22d3ee', '#a78bfa', '#f472b6',
    '#fb923c', '#facc15', '#f87171', '#94a3b8',
  ];

  // Map device ID → group color for tile border
  let deviceGroupColor = $derived.by(() => {
    const map = new Map<string, string>();
    for (const g of groups) {
      for (const did of g.device_ids) {
        map.set(did, g.color);
      }
    }
    return map;
  });

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
        return { metric: s?.power_w != null ? s.power_w.toFixed(0) : '—', unit: 'W' };
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
    const s = sensorData[d.id];
    if (!s) return false; // default off until data loads
    if (s.output != null) return s.output > 0;
    // Infer from power: >0.5W means on
    if (s.power_w != null) return s.power_w > 0.5;
    return false;
  }

  async function handleToggle(d: Device) {
    const current = switchState(d);
    const next = current == null ? true : !current;
    try {
      await post(`/api/device/${d.id}/command`, {
        method: 'Switch.Set',
        params: { id: 0, on: next }
      });
      sensorData = { ...sensorData, [d.id]: { ...(sensorData[d.id] ?? {}), output: next ? 1 : 0 } };
    } catch { /* ignore, real state will sync on next poll */ }
  }


  // ── Group management ────────────────────────────────────────────────────────
  async function loadGroups() {
    try {
      const res = await getGroups();
      groups = res.groups;
    } catch { /* ignore */ }
  }

  function startNewGroup() {
    groupEditId = 'new';
    groupForm = { name: '', category: 'light', device_ids: [], color: '#4ade80' };
  }

  function startEditGroup(g: DeviceGroup) {
    groupEditId = g.id;
    groupForm = { name: g.name, category: g.category, device_ids: [...g.device_ids], color: g.color };
  }

  function cancelGroup() {
    groupEditId = null;
  }

  function toggleGroupDevice(deviceId: string) {
    if (groupForm.device_ids.includes(deviceId)) {
      groupForm.device_ids = groupForm.device_ids.filter(id => id !== deviceId);
    } else {
      groupForm.device_ids = [...groupForm.device_ids, deviceId];
    }
  }

  async function saveGroup() {
    const body = { name: groupForm.name.trim(), category: groupForm.category, device_ids: groupForm.device_ids, color: groupForm.color };
    if (!body.name) return;
    try {
      if (groupEditId === 'new') {
        const created = await createGroup(body);
        groups = [...groups, created];
      } else if (groupEditId) {
        const updated = await updateGroup(groupEditId, body);
        groups = groups.map(g => g.id === groupEditId ? updated : g);
      }
      groupEditId = null;
    } catch { /* keep form open on error */ }
  }

  async function removeGroup(id: string) {
    if (!window.confirm('Delete this group?')) return;
    try {
      await deleteGroup(id);
      groups = groups.filter(g => g.id !== id);
    } catch { /* ignore */ }
  }

  // ── Group switch state + toggle ──────────────────────────────────────────
  function groupSwitchState(g: DeviceGroup): 'all-on' | 'all-off' | 'mixed' {
    const controllable = g.device_ids
      .map(id => devices.find(d => d.id === id))
      .filter((d): d is Device => d != null && isControllable(d));
    if (!controllable.length) return 'all-off';
    const onCount = controllable.filter(d => switchState(d)).length;
    if (onCount === controllable.length) return 'all-on';
    if (onCount === 0) return 'all-off';
    return 'mixed';
  }

  function groupOnCount(g: DeviceGroup): { on: number; total: number } {
    const controllable = g.device_ids
      .map(id => devices.find(d => d.id === id))
      .filter((d): d is Device => d != null && isControllable(d));
    const on = controllable.filter(d => switchState(d)).length;
    return { on, total: controllable.length };
  }

  async function handleGroupToggle(g: DeviceGroup) {
    const state = groupSwitchState(g);
    const targetOn = state !== 'all-on';
    const controllable = g.device_ids
      .map(id => devices.find(d => d.id === id))
      .filter((d): d is Device => d != null && isControllable(d));
    if (!controllable.length) return;
    if (!window.confirm(`Turn ${targetOn ? 'on' : 'off'} all ${controllable.length} devices in ${g.name}?`)) return;
    await Promise.allSettled(
      controllable.map(async d => {
        try {
          await post(`/api/device/${d.id}/command`, {
            method: 'Switch.Set',
            params: { id: 0, on: targetOn }
          });
          sensorData = { ...sensorData, [d.id]: { ...(sensorData[d.id] ?? {}), output: targetOn ? 1 : 0 } };
        } catch { /* ignore individual failures */ }
      })
    );
  }

  // ── Dimmer control ──────────────────────────────────────────────────────
  let dimmerTimers = new Map<string, ReturnType<typeof setTimeout>>();

  function handleDimmer(d: Device, pct: number) {
    // Optimistic local update
    sensorData = { ...sensorData, [d.id]: { ...(sensorData[d.id] ?? {}), brightness: pct } };
    // Debounce API call
    const existing = dimmerTimers.get(d.id);
    if (existing) clearTimeout(existing);
    dimmerTimers.set(d.id, setTimeout(async () => {
      dimmerTimers.delete(d.id);
      try {
        await post(`/api/device/${d.id}/command`, {
          method: 'Light.Set',
          params: { id: 0, brightness: pct }
        });
      } catch { /* ignore */ }
    }, 300));
  }

  // ── Data loading ───────────────────────────────────────────────────────────
  async function loadSensors() {
    if (!devices.length) return;
    const batch: Record<string, Record<string, number>> = {};
    await Promise.allSettled(
      devices.map(async d => {
        try {
          const res = await get<ReadingsResponse>(`/api/readings/${d.id}?limit=10`);
          if (res.readings?.length) {
            const latest: Record<string, number> = {};
            for (const r of res.readings) {
              if (!(r.metric in latest)) latest[r.metric] = r.value;
            }
            batch[d.id] = latest;
          }
        } catch { /* device has no readings yet */ }
      })
    );
    sensorData = { ...sensorData, ...batch };
  }

  async function loadSchedule() {
    try {
      const plan = await get<DayPlanResponse>('/api/schedule/today');
      if (plan.recipe_name) {
        recipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(plan.recipe_name)}`);
      }
    } catch { /* no active recipe */ }
  }

  async function refresh() {
    try {
      const [statusRes, alertsRes] = await Promise.all([
        get<StatusResponse>('/api/status'),
        get<AlertsResponse>('/api/alerts')
      ]);
      devices = statusRes.devices;
      alerts = alertsRes.alerts;
    } catch { /* ignore */ }

    await loadSensors();
    await loadGroups();
  }

  onMount(() => {
    refresh();
    loadSchedule();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'device_status' || evt?.type === 'sensor_update') {
      refresh();
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
                      onblur={() => saveEdit(d)}
                    />
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
                    onEdit={editingId !== d.id ? () => startEdit(d) : undefined}
                    groupColor={deviceGroupColor.get(d.id)}
                    dimmerValue={d.device_type === 'shelly_dimmer' ? (sensorData[d.id]?.brightness ?? 0) : undefined}
                    onDimmer={d.device_type === 'shelly_dimmer' ? (pct: number) => handleDimmer(d, pct) : undefined}
                  />
                </div>
              {/each}
            </div>
          </section>
        {/if}
      {/each}

    </div>

    <!-- Sidebar: PolarRing + Groups -->
    <aside class="sidebar">
      {#if recipe}
        <div class="sidebar-panel recipe-panel">
          <div class="group-header">{recipe.name}</div>
          <div class="polar-center">
            <PolarRing {recipe} {nowMin} size="md" />
          </div>
        </div>
      {/if}

      <div class="sidebar-panel groups-panel">
        <div class="groups-sidebar-header">
          <span class="group-header">Groups</span>
          {#if groupEditId === null}
            <button class="btn-add-group" onclick={startNewGroup}>+ New</button>
          {/if}
        </div>

        {#if groups.length === 0 && groupEditId === null}
          <p class="empty-state">No groups defined</p>
        {/if}

        {#each groups as g (g.id)}
          {#if groupEditId === g.id}
            <div class="group-form">
              <input class="group-name-input" bind:value={groupForm.name} placeholder="Group name" />
              <select class="group-category-select" bind:value={groupForm.category}>
                <option value="light">Light</option>
                <option value="irrigation">Irrigation</option>
                <option value="climate">Climate</option>
                <option value="other">Other</option>
              </select>
              <div class="color-palette">
                {#each GROUP_COLORS as c}
                  <button
                    class="color-swatch"
                    class:active={groupForm.color === c}
                    style="background: {c}"
                    onclick={() => { groupForm.color = c; }}
                    aria-label="Color {c}"
                  ></button>
                {/each}
              </div>
              <div class="group-device-list">
                {#each devices as d (d.id)}
                  <label class="group-device-check">
                    <input
                      type="checkbox"
                      checked={groupForm.device_ids.includes(d.id)}
                      onchange={() => toggleGroupDevice(d.id)}
                    />
                    <span>{d.name}</span>
                  </label>
                {/each}
              </div>
              <div class="group-form-actions">
                <button class="btn-group-save" onclick={saveGroup}>Save</button>
                <button class="btn-group-cancel" onclick={cancelGroup}>Cancel</button>
              </div>
            </div>
          {:else}
            {@const gs = groupSwitchState(g)}
            {@const counts = groupOnCount(g)}
            <div class="group-row-wrap">
              <div class="group-row">
                <span class="group-row-dot" style="background: {g.color}"></span>
                <span class="group-row-name">{g.name}</span>
                <StatusDot variant={gs === 'all-on' ? 'ok' : gs === 'all-off' ? 'crit' : 'warn'} />
                <button
                  class="group-toggle"
                  class:on={gs === 'all-on'}
                  class:mixed={gs === 'mixed'}
                  onclick={() => handleGroupToggle(g)}
                  aria-label={gs === 'all-on' ? 'Turn off group' : 'Turn on group'}
                >
                  <span class="group-toggle-thumb"></span>
                </button>
                <button class="btn-group-action" onclick={() => startEditGroup(g)}>Edit</button>
                <button class="btn-group-action btn-group-delete" onclick={() => removeGroup(g.id)}>✕</button>
              </div>
              <div class="group-row-status" class:st-ok={gs === 'all-on'} class:st-warn={gs === 'mixed'} class:st-crit={gs === 'all-off'}>
                {#if counts.total > 0}
                  {counts.on}/{counts.total} on
                {:else}
                  no controllable devices
                {/if}
              </div>
            </div>
          {/if}
        {/each}

        {#if groupEditId === 'new'}
          <div class="group-form">
            <input class="group-name-input" bind:value={groupForm.name} placeholder="Group name" />
            <select class="group-category-select" bind:value={groupForm.category}>
              <option value="light">Light</option>
              <option value="irrigation">Irrigation</option>
              <option value="climate">Climate</option>
              <option value="other">Other</option>
            </select>
            <div class="color-palette">
              {#each GROUP_COLORS as c}
                <button
                  class="color-swatch"
                  class:active={groupForm.color === c}
                  style="background: {c}"
                  onclick={() => { groupForm.color = c; }}
                  aria-label="Color {c}"
                ></button>
              {/each}
            </div>
            <div class="group-device-list">
              {#each devices as d (d.id)}
                <label class="group-device-check">
                  <input
                    type="checkbox"
                    checked={groupForm.device_ids.includes(d.id)}
                    onchange={() => toggleGroupDevice(d.id)}
                  />
                  <span>{d.name}</span>
                </label>
              {/each}
            </div>
            <div class="group-form-actions">
              <button class="btn-group-save" onclick={saveGroup}>Save</button>
              <button class="btn-group-cancel" onclick={cancelGroup}>Cancel</button>
            </div>
          </div>
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


  .empty-state {
    font-size: var(--t-11);
    color: var(--ink-4);
    margin: 0;
    text-align: center;
    padding: var(--s-4) 0;
  }

  /* ── Groups section (sidebar) ─────────────────────────────────────────── */
  .groups-sidebar-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .btn-add-group {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 2px var(--s-3);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.6;
    transition: color 0.1s, border-color 0.1s;
  }

  .btn-add-group:hover {
    color: var(--ink-1);
    border-color: var(--ink-3);
  }

  .group-row {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-2) 0;
    border-bottom: 1px solid var(--line);
  }

  .group-row:last-child {
    border-bottom: none;
  }

  .group-row-name {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-1);
    flex: 1;
  }

  .group-category-chip {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    padding: 1px 6px;
    border-radius: var(--r-pill);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1.6;
    background: var(--bg-3);
    color: var(--ink-3);
    border: 1px solid var(--line);
  }

  .group-category-chip--light {
    background: var(--accent-soft);
    color: var(--accent);
    border-color: var(--accent-line);
  }

  .group-row-count {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    white-space: nowrap;
  }

  .btn-group-action {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 1px 6px;
    cursor: pointer;
    line-height: 1.6;
    transition: color 0.1s, border-color 0.1s;
  }

  .btn-group-action:hover {
    color: var(--ink-1);
    border-color: var(--ink-3);
  }

  .btn-group-delete:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
    background: var(--st-crit-soft);
  }

  .group-form {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    padding: var(--s-3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    margin-top: var(--s-2);
  }

  .group-name-input {
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font-family: var(--font-mono);
    font-size: var(--t-12);
    padding: var(--s-2) var(--s-3);
    outline: none;
  }

  .group-name-input:focus {
    border-color: var(--accent-line);
  }

  .group-category-select {
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    padding: var(--s-2) var(--s-3);
    cursor: pointer;
    outline: none;
    align-self: flex-start;
  }

  .group-category-select:focus {
    border-color: var(--accent-line);
  }

  .group-device-list {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-2);
  }

  .group-device-check {
    display: flex;
    align-items: center;
    gap: var(--s-1);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-2);
    cursor: pointer;
  }

  .group-form-actions {
    display: flex;
    gap: var(--s-2);
  }

  .btn-group-save {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    background: var(--accent);
    color: var(--bg-0);
    border: none;
    border-radius: var(--r-1);
    padding: var(--s-1) var(--s-4);
    cursor: pointer;
    letter-spacing: 0.06em;
  }

  .btn-group-cancel {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    background: none;
    color: var(--ink-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: var(--s-1) var(--s-4);
    cursor: pointer;
    letter-spacing: 0.06em;
  }

  /* ── Color palette ──────────────────────────────────────────────────────── */
  .color-palette {
    display: flex;
    gap: var(--s-2);
    flex-wrap: wrap;
  }

  .color-swatch {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    border: 2px solid transparent;
    cursor: pointer;
    transition: border-color 0.1s, transform 0.1s;
    padding: 0;
  }

  .color-swatch.active {
    border-color: var(--ink-1);
    transform: scale(1.15);
  }

  .color-swatch:hover:not(.active) {
    border-color: var(--ink-3);
  }

  .group-row-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  /* ── Group row wrap (row + status line) ──────────────────────────────── */
  .group-row-wrap {
    display: flex;
    flex-direction: column;
    border-bottom: 1px solid var(--line);
    padding-bottom: var(--s-2);
  }

  .group-row-wrap:last-child {
    border-bottom: none;
  }

  .group-row-wrap .group-row {
    border-bottom: none;
  }

  .group-row-status {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    letter-spacing: 0.04em;
    padding-left: calc(10px + var(--s-3));
    line-height: 1.4;
  }

  .group-row-status.st-ok { color: var(--st-ok); }
  .group-row-status.st-warn { color: var(--st-warn); }
  .group-row-status.st-crit { color: var(--st-crit); }

  /* ── Group toggle switch ─────────────────────────────────────────────── */
  .group-toggle {
    flex-shrink: 0;
    position: relative;
    width: 28px;
    height: 16px;
    border-radius: var(--r-pill);
    background: var(--line);
    border: none;
    cursor: pointer;
    padding: 0;
    transition: background 0.15s;
  }

  .group-toggle.on {
    background: var(--accent);
  }

  .group-toggle.mixed {
    background: var(--st-warn);
  }

  .group-toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--bg-0);
    transition: transform 0.15s;
  }

  .group-toggle.on .group-toggle-thumb {
    transform: translateX(12px);
  }

  .group-toggle.mixed .group-toggle-thumb {
    transform: translateX(6px);
  }
</style>
