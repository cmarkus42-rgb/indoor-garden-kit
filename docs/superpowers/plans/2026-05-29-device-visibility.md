# Device Visibility & Dashboard Control — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add global device enable/disable, per-view visibility control, interactive chart line toggling, and a consistent time-range slider across all chart views.

**Architecture:** Two new columns on Device model (`enabled`, `view_visibility`) with a PATCH API endpoint. Frontend filters devices per view, extracts time-range slider as shared component, and adds click-to-toggle on chart legends via uPlot's native `series.show`.

**Tech Stack:** Python/FastAPI/SQLModel/Alembic (backend), SvelteKit 5/TypeScript/uPlot (frontend)

**Repos:**
- Backend: `cipher-grow-kit` at `/Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit`
- Frontend: `indoor-garden-kit` at `/Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit`, dashboard in `packages/grow-dashboard`

---

## Task 1: Backend — Migration + Model

**Files:**
- Modify: `cipher-grow-kit/src/orchestrator/db/models.py:19-31`
- Create: `cipher-grow-kit/src/orchestrator/db/migrations/versions/004_device_visibility.py`

- [ ] **Step 1: Add columns to Device model**

In `src/orchestrator/db/models.py`, add two fields to the `Device` class after line 31 (`status`):

```python
class Device(SQLModel, table=True):
    __tablename__ = "devices"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    device_type: DeviceType = Field(sa_column=Column(String, nullable=False))
    address: str
    zone: str | None = None
    config: dict = Field(default_factory=dict, sa_column=Column(JSON, default={}))
    last_seen: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    status: str = Field(default="online")
    enabled: bool = Field(default=True)
    view_visibility: dict = Field(default_factory=dict, sa_column=Column(JSON, default={}))
```

- [ ] **Step 2: Create migration 004**

Create `src/orchestrator/db/migrations/versions/004_device_visibility.py`:

```python
"""Add enabled and view_visibility columns to devices

Revision ID: 004
Revises: 003
Create Date: 2026-05-29
"""

from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("devices", sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("1")))
    op.add_column("devices", sa.Column("view_visibility", sa.JSON(), server_default="{}"))


def downgrade() -> None:
    op.drop_column("devices", "view_visibility")
    op.drop_column("devices", "enabled")
```

- [ ] **Step 3: Run migration**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
python -m alembic upgrade head
```

Expected: migration applies cleanly, all existing devices get `enabled=true`, `view_visibility={}`.

- [ ] **Step 4: Run existing tests**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
python -m pytest tests/ -x -q
```

Expected: 196 tests pass (no regressions).

- [ ] **Step 5: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
git add src/orchestrator/db/models.py src/orchestrator/db/migrations/versions/004_device_visibility.py
git commit -m "feat(db): add enabled + view_visibility to Device model (migration 004)"
```

---

## Task 2: Backend — PATCH API + Status Serialization

**Files:**
- Modify: `cipher-grow-kit/src/orchestrator/api/device.py`
- Modify: `cipher-grow-kit/src/orchestrator/api/status.py`

- [ ] **Step 1: Add PATCH endpoint to device.py**

Add at the end of `src/orchestrator/api/device.py`:

```python
class DeviceConfigRequest(BaseModel):
    enabled: bool | None = None
    view_visibility: dict[str, bool] | None = None


@router.patch("/device/{device_id}/config")
async def update_device_config(
    device_id: uuid.UUID,
    body: DeviceConfigRequest,
    session: AsyncSession = Depends(get_session),
):
    device = await session.get(Device, device_id)
    if not device:
        raise HTTPException(status_code=404, detail="Device not found")

    if body.enabled is not None:
        device.enabled = body.enabled

    if body.view_visibility is not None:
        merged = {**device.view_visibility, **body.view_visibility}
        device.view_visibility = merged

    session.add(device)
    await session.commit()
    await session.refresh(device)
    return {
        "id": str(device.id),
        "name": device.name,
        "device_type": device.device_type,
        "address": device.address,
        "zone": device.zone,
        "status": device.status,
        "last_seen": device.last_seen.isoformat(),
        "enabled": device.enabled,
        "view_visibility": device.view_visibility,
    }
```

- [ ] **Step 2: Update status serialization**

In `src/orchestrator/api/status.py`, add `enabled` and `view_visibility` to the device dict (lines 18-27):

```python
@router.get("/status")
async def get_status(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(Device))
    devices = result.all()
    return {
        "devices": [
            {
                "id": str(d.id),
                "name": d.name,
                "device_type": d.device_type,
                "address": d.address,
                "zone": d.zone,
                "status": d.status,
                "last_seen": d.last_seen.isoformat(),
                "enabled": d.enabled,
                "view_visibility": d.view_visibility,
            }
            for d in devices
        ]
    }
```

- [ ] **Step 3: Run tests**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
python -m pytest tests/ -x -q
```

Expected: 196 tests pass.

- [ ] **Step 4: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
git add src/orchestrator/api/device.py src/orchestrator/api/status.py
git commit -m "feat(api): PATCH /device/{id}/config + enabled/view_visibility in status"
```

---

## Task 3: Frontend — Types + Visibility Helper + API patch

**Files:**
- Modify: `packages/grow-dashboard/src/lib/types.ts`
- Create: `packages/grow-dashboard/src/lib/visibility.ts`
- Modify: `packages/grow-dashboard/src/lib/api.ts`

- [ ] **Step 1: Extend Device interface**

In `packages/grow-dashboard/src/lib/types.ts`, add two fields to the `Device` interface:

```typescript
export interface Device {
  id: string;
  name: string;
  device_type: string;
  address: string;
  zone: string;
  status: string;
  last_seen: string;
  enabled: boolean;
  view_visibility: Record<string, boolean>;
}
```

- [ ] **Step 2: Create visibility helper**

Create `packages/grow-dashboard/src/lib/visibility.ts`:

```typescript
import type { Device } from '$lib/types.js';

export function visibleDevices(devices: Device[], view: string): Device[] {
  return devices.filter(d => d.enabled && d.view_visibility[view] !== false);
}
```

- [ ] **Step 3: Add `patch` to api.ts**

In `packages/grow-dashboard/src/lib/api.ts`, add after the `del` function:

```typescript
export function patch<T>(path: string, body: unknown): Promise<T> {
  return request<T>('PATCH', path, body);
}
```

- [ ] **Step 4: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/lib/types.ts packages/grow-dashboard/src/lib/visibility.ts packages/grow-dashboard/src/lib/api.ts
git commit -m "feat(lib): Device visibility types, filter helper, PATCH api"
```

---

## Task 4: Frontend — Settings UI (Enable Toggle + View Checkboxes)

**Files:**
- Modify: `packages/grow-dashboard/src/routes/settings/+page.svelte:245-272`

- [ ] **Step 1: Add imports and state**

At the top of the `<script>` block (after existing imports), add:

```typescript
import { patch } from '$lib/api.js';

const VIEW_KEYS = ['overview', 'investigate', 'energy', 'ventilation', 'recipes'] as const;
let expandedDevice = $state<string | null>(null);
```

- [ ] **Step 2: Add toggle handler functions**

After the `loadData` function:

```typescript
async function toggleEnabled(d: Device) {
  const updated = await patch<Device>(`/api/device/${d.id}/config`, {
    enabled: !d.enabled,
  });
  devices = devices.map(dev => dev.id === d.id ? updated : dev);
}

async function toggleViewVisibility(d: Device, view: string) {
  const current = d.view_visibility[view] !== false;
  const updated = await patch<Device>(`/api/device/${d.id}/config`, {
    view_visibility: { [view]: !current },
  });
  devices = devices.map(dev => dev.id === d.id ? updated : dev);
}
```

- [ ] **Step 3: Replace device-row template**

Replace the `<!-- SECTION: Devices -->` section (lines 245-272) with:

```svelte
<!-- SECTION: Devices -->
<section class="settings-section">
  <div class="section-h">Devices</div>
  {#if devices.length === 0}
    <div class="section-body">
      <span class="muted mono small">No devices</span>
    </div>
  {:else}
    <div class="device-list">
      {#each devices as d}
        {@const st = deviceStatus(d.status)}
        <div class="device-row" class:device-disabled={!d.enabled}>
          <div class="device-left">
            <button
              class="toggle-btn"
              class:toggle-on={d.enabled}
              onclick={() => toggleEnabled(d)}
              aria-label={d.enabled ? 'Disable device' : 'Enable device'}
            >
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </button>
            <StatusDot variant={st} live={st === 'ok'} />
            <div class="device-info">
              <span class="device-name">{d.name}</span>
              <span class="device-type mono muted">{d.device_type}</span>
            </div>
          </div>
          <div class="device-right">
            <Chip>{d.zone}</Chip>
            <Chip variant={st}>{d.status}</Chip>
            <button
              class="btn-ghost-sm"
              onclick={() => expandedDevice = expandedDevice === d.id ? null : d.id}
              aria-label="Toggle view visibility"
            >
              {expandedDevice === d.id ? '▾' : '▸'} Views
            </button>
          </div>
        </div>
        {#if expandedDevice === d.id}
          <div class="device-views">
            {#each VIEW_KEYS as view}
              <label class="view-check" class:view-check-disabled={!d.enabled}>
                <input
                  type="checkbox"
                  checked={d.view_visibility[view] !== false}
                  disabled={!d.enabled}
                  onchange={() => toggleViewVisibility(d, view)}
                />
                <span class="view-label">{view}</span>
              </label>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
</section>
```

- [ ] **Step 4: Add styles**

Add inside the `<style>` block:

```css
/* Device toggle */
.toggle-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  flex-shrink: 0;
}

.toggle-track {
  display: flex;
  align-items: center;
  width: 32px;
  height: 18px;
  border-radius: 9px;
  background: var(--ink-1);
  padding: 2px;
  transition: background 0.15s;
}

.toggle-on .toggle-track {
  background: oklch(68% 0.16 145);
}

.toggle-thumb {
  display: block;
  width: 14px;
  height: 14px;
  border-radius: 50%;
  background: var(--bg-0);
  transition: transform 0.15s;
}

.toggle-on .toggle-thumb {
  transform: translateX(14px);
}

.device-disabled {
  opacity: 0.45;
}

/* View visibility checkboxes */
.device-views {
  display: flex;
  gap: var(--s-4);
  padding: 0 var(--s-4) var(--s-3) calc(var(--s-4) + 40px);
  flex-wrap: wrap;
}

.view-check {
  display: flex;
  align-items: center;
  gap: var(--s-1);
  cursor: pointer;
  font-family: var(--font-mono);
  font-size: var(--t-11);
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--ink-3);
}

.view-check-disabled {
  opacity: 0.4;
  pointer-events: none;
}

.view-label {
  user-select: none;
}
```

- [ ] **Step 5: Verify in browser**

Open `http://localhost:5173/settings`. Check:
- Each device has an enable/disable toggle
- Clicking toggle greys out the device
- "Views" button expands checkbox row
- Toggling a view checkbox sends PATCH and updates state
- Disabled device has disabled checkboxes

- [ ] **Step 6: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/settings/+page.svelte
git commit -m "feat(settings): device enable/disable toggle + per-view visibility checkboxes"
```

---

## Task 5: Frontend — Apply Visibility Filter to All Views

**Files:**
- Modify: `packages/grow-dashboard/src/routes/+page.svelte:120-126`
- Modify: `packages/grow-dashboard/src/routes/investigate/+page.svelte`
- Modify: `packages/grow-dashboard/src/routes/energy/+page.svelte`
- Modify: `packages/grow-dashboard/src/routes/ventilation/+page.svelte`
- Modify: `packages/grow-dashboard/src/routes/recipes/[name]/+page.svelte`

- [ ] **Step 1: Overview (+page.svelte)**

Add import at the top of the script:

```typescript
import { visibleDevices } from '$lib/visibility.js';
```

Change lines 122-126 from:

```typescript
climateDevices = status.devices.filter(
  d => d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor'
);
soilDevices = status.devices.filter(d => d.device_type === 'ecowitt_sensor');
```

To:

```typescript
const visible = visibleDevices(status.devices, 'overview');
climateDevices = visible.filter(
  d => d.device_type === 'blu_ht' || d.device_type === 'ecowitt_indoor'
);
soilDevices = visible.filter(d => d.device_type === 'ecowitt_sensor');
```

- [ ] **Step 2: Investigate**

In `src/routes/investigate/+page.svelte`, add import:

```typescript
import { visibleDevices } from '$lib/visibility.js';
```

Find where `devices` is loaded from `/api/status` and filter:

```typescript
devices = visibleDevices(status.devices, 'investigate');
```

- [ ] **Step 3: Energy**

In `src/routes/energy/+page.svelte`, add import:

```typescript
import { visibleDevices } from '$lib/visibility.js';
```

Change plug filter from:

```typescript
plugs = status.devices.filter(d => d.device_type === 'shelly_plug');
```

To:

```typescript
plugs = visibleDevices(status.devices, 'energy').filter(d => d.device_type === 'shelly_plug');
```

- [ ] **Step 4: Ventilation**

In `src/routes/ventilation/+page.svelte`, add import:

```typescript
import { visibleDevices } from '$lib/visibility.js';
```

Filter devices where they are loaded:

```typescript
const visible = visibleDevices(status.devices, 'ventilation');
```

Use `visible` instead of `status.devices` for controller list.

- [ ] **Step 5: Recipes**

In `src/routes/recipes/[name]/+page.svelte`, add import:

```typescript
import { visibleDevices } from '$lib/visibility.js';
```

Filter devices where groups are loaded, using `'recipes'` as view key.

- [ ] **Step 6: Verify in browser**

1. Go to Settings, disable a device
2. Check Overview — device should not appear
3. Go to Settings, re-enable device but set Overview to hidden
4. Check Overview — device hidden. Check Investigate — device visible.

- [ ] **Step 7: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/+page.svelte \
  packages/grow-dashboard/src/routes/investigate/+page.svelte \
  packages/grow-dashboard/src/routes/energy/+page.svelte \
  packages/grow-dashboard/src/routes/ventilation/+page.svelte \
  'packages/grow-dashboard/src/routes/recipes/[name]/+page.svelte'
git commit -m "feat(views): apply visibleDevices filter to all views"
```

---

## Task 6: Frontend — TimeRangeSlider Component + Bugfix

**Files:**
- Create: `packages/grow-dashboard/src/lib/components/TimeRangeSlider.svelte`
- Modify: `packages/grow-dashboard/src/routes/+page.svelte:184-211,485-494,903-949`

- [ ] **Step 1: Create TimeRangeSlider component**

Create `packages/grow-dashboard/src/lib/components/TimeRangeSlider.svelte`:

```svelte
<script lang="ts" module>
  import type uPlot from 'uplot';

  export const LOG_STEPS = [
    { seconds: 3600,        label: 'Last hour' },
    { seconds: 10800,       label: 'Last 3 hours' },
    { seconds: 21600,       label: 'Last 6 hours' },
    { seconds: 43200,       label: 'Last 12 hours' },
    { seconds: 86400,       label: 'Last 24 hours' },
    { seconds: 259200,      label: 'Last 3 days' },
    { seconds: 604800,      label: 'Last 7 days' },
    { seconds: 1209600,     label: 'Last 14 days' },
    { seconds: 2592000,     label: 'Last 30 days' },
    { seconds: 15552000,    label: 'Last 6 months' },
    { seconds: 31536000,    label: 'Last year' },
    { seconds: Infinity,    label: 'All data' },
  ] as const;

  export function filterByRange(rangeStep: number, aligned: uPlot.AlignedData): uPlot.AlignedData {
    const step = LOG_STEPS[rangeStep];
    if (step.seconds === Infinity || !aligned[0]?.length) return aligned;
    const xs = aligned[0] as number[];
    const cutoff = Math.round(Date.now() / 1000) - step.seconds;
    const startIdx = xs.findIndex(t => t >= cutoff);
    if (startIdx < 0) return aligned;
    return aligned.map(arr => (arr as number[]).slice(startIdx)) as uPlot.AlignedData;
  }
</script>

<script lang="ts">
  interface Props {
    value?: number;
  }

  let { value = $bindable(4) }: Props = $props();

  let label = $derived(LOG_STEPS[value].label);
</script>

<div class="time-slider-wrap">
  <input
    type="range"
    class="time-slider"
    min="0"
    max={LOG_STEPS.length - 1}
    bind:value={value}
  />
  <span class="time-slider-label">{label}</span>
</div>

<style>
  .time-slider-wrap {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: 0 var(--s-2);
  }

  .time-slider {
    flex: 1;
    appearance: none;
    height: 4px;
    border-radius: 2px;
    background: var(--line);
    outline: none;
    cursor: pointer;
  }

  .time-slider::-webkit-slider-thumb {
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: oklch(72% 0.16 145);
    border: 2px solid var(--bg-0);
    cursor: pointer;
    transition: transform 0.1s;
  }

  .time-slider::-webkit-slider-thumb:hover {
    transform: scale(1.2);
  }

  .time-slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: oklch(72% 0.16 145);
    border: 2px solid var(--bg-0);
    cursor: pointer;
  }

  .time-slider-label {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-3);
    white-space: nowrap;
    min-width: 100px;
    text-align: right;
  }
</style>
```

- [ ] **Step 2: Refactor Overview to use component**

In `src/routes/+page.svelte`:

Add import:

```typescript
import TimeRangeSlider, { filterByRange } from '$lib/components/TimeRangeSlider.svelte';
```

Remove the inline `LOG_STEPS` array (lines 185-198), `rangeLabel` derived (line 201), and `filterByRange` function (lines 203-211).

Change `rangeStep` default (line 200):

```typescript
let rangeStep = $state(4);  // default: "Last 24 hours" (BUGFIX: was 0 = "Last hour")
```

Update the filtered data derivation (lines 363-364):

```typescript
let climateChartFiltered = $derived(filterByRange(rangeStep, climateChart.data));
let moistureChartFiltered = $derived(filterByRange(rangeStep, moistureChart.data));
```

Replace the inline slider HTML (lines 485-494):

```svelte
<TimeRangeSlider bind:value={rangeStep} />
```

Remove the inline slider CSS (lines 903-949, the `.time-slider-wrap`, `.time-slider`, `.time-slider-label` rules).

- [ ] **Step 3: Verify Overview slider works**

Open `http://localhost:5173`. Slider should:
- Default to "Last 24 hours" (not "Last hour")
- Moving slider changes chart time range
- Charts show data matching the selected range

- [ ] **Step 4: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/lib/components/TimeRangeSlider.svelte \
  packages/grow-dashboard/src/routes/+page.svelte
git commit -m "feat(ui): extract TimeRangeSlider component, fix default to 24h"
```

---

## Task 7: Frontend — Add TimeRangeSlider to Remaining Views

**Files:**
- Modify: `packages/grow-dashboard/src/routes/investigate/+page.svelte`
- Modify: `packages/grow-dashboard/src/routes/energy/+page.svelte`
- Modify: `packages/grow-dashboard/src/routes/ventilation/+page.svelte`

- [ ] **Step 1: Investigate**

In `src/routes/investigate/+page.svelte`, add:

```typescript
import TimeRangeSlider, { filterByRange } from '$lib/components/TimeRangeSlider.svelte';

let rangeStep = $state(4);
```

Before the `<TimeChart>` component, add:

```svelte
<TimeRangeSlider bind:value={rangeStep} />
```

Where chart data is passed to `<TimeChart>`, wrap it:

```svelte
<TimeChart data={filterByRange(rangeStep, chartData)} series={chartSeries} />
```

- [ ] **Step 2: Energy**

In `src/routes/energy/+page.svelte`, add the same pattern:

```typescript
import TimeRangeSlider, { filterByRange } from '$lib/components/TimeRangeSlider.svelte';

let rangeStep = $state(4);
```

Add `<TimeRangeSlider bind:value={rangeStep} />` before charts. Apply `filterByRange(rangeStep, data)` to chart data prop.

- [ ] **Step 3: Ventilation**

In `src/routes/ventilation/+page.svelte`, add the same pattern:

```typescript
import TimeRangeSlider, { filterByRange } from '$lib/components/TimeRangeSlider.svelte';

let rangeStep = $state(4);
```

Add `<TimeRangeSlider bind:value={rangeStep} />` before charts. Apply `filterByRange(rangeStep, data)` to chart data prop.

- [ ] **Step 4: Verify all views**

Check each view:
- Investigate: slider visible, chart responds to range changes
- Energy: slider visible, chart responds to range changes
- Ventilation: slider visible, chart responds to range changes

- [ ] **Step 5: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/investigate/+page.svelte \
  packages/grow-dashboard/src/routes/energy/+page.svelte \
  packages/grow-dashboard/src/routes/ventilation/+page.svelte
git commit -m "feat(ui): add TimeRangeSlider to investigate, energy, ventilation views"
```

---

## Task 8: Frontend — Chart Legend Click Toggle

**Files:**
- Modify: `packages/grow-dashboard/src/lib/components/TimeChart.svelte`

- [ ] **Step 1: Add series visibility state and toggle function**

In `TimeChart.svelte`, add after the `tooltipHtml` state (line 36):

```typescript
let seriesVisible = $state<boolean[]>([]);
```

After `chart` is created in `onMount` (line 139), add:

```typescript
seriesVisible = series.map(() => true);
```

Add toggle function after `updateTooltip`:

```typescript
function toggleSeries(idx: number) {
  if (!chart) return;
  const newShow = !chart.series[idx].show;
  chart.setSeries(idx, { show: newShow });
  seriesVisible = seriesVisible.map((v, i) => i === idx ? newShow : v);
}
```

- [ ] **Step 2: Add legend HTML**

After the closing `</div>` of `chart-wrap` (line 194), add:

```svelte
{#if series.length > 1}
  <div class="chart-legend">
    {#each series.slice(1) as s, i}
      {@const idx = i + 1}
      {@const color = typeof s.stroke === 'string' ? s.stroke : '#888'}
      <button
        class="legend-item"
        class:legend-hidden={seriesVisible[idx] === false}
        onclick={() => toggleSeries(idx)}
      >
        <span class="legend-dot" style="background:{color}"></span>
        <span class="legend-label">{s.label ?? `Series ${idx}`}</span>
      </button>
    {/each}
  </div>
{/if}
```

- [ ] **Step 3: Add legend styles**

Add inside the `<style>` block:

```css
.chart-legend {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-1, 4px) var(--s-3, 12px);
  padding: var(--s-2, 8px) var(--s-2, 8px) var(--s-1, 4px);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 4px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 3px;
  font-family: var(--font-mono, 'JetBrains Mono', monospace);
  font-size: 10px;
  color: var(--ink-3, #7a9a7e);
  transition: opacity 0.15s;
}

.legend-item:hover {
  background: var(--bg-2, rgba(0,0,0,0.05));
}

.legend-hidden {
  opacity: 0.35;
}

.legend-dot {
  display: inline-block;
  width: 8px;
  height: 3px;
  border-radius: 1px;
  flex-shrink: 0;
}

.legend-label {
  user-select: none;
}
```

- [ ] **Step 4: Reset visibility on series changes**

In the `$effect` block (line 157), after chart recreation, reset `seriesVisible`:

```typescript
$effect(() => {
  const d = data;
  const s = series;
  if (!chart || !container) return;

  if (s.length !== chart.series.length) {
    ondestroy?.();
    chart.destroy();
    const w = container.offsetWidth || 600;
    chart = new uPlot(buildOpts(w), d, container);
    onready?.(chart);
    seriesVisible = s.map(() => true);
    return;
  }

  try {
    chart.setData(d);
  } catch {
    chart.destroy();
    const w = container.offsetWidth || 600;
    chart = new uPlot(buildOpts(w), d, container);
    onready?.(chart);
    seriesVisible = s.map(() => true);
  }
});
```

- [ ] **Step 5: Verify**

Open any chart view. Below each chart:
- Legend items with colored dots and labels
- Click a sensor label — its line disappears from chart, label dims
- Click again — line reappears
- Works on Overview, Investigate, Energy, Ventilation (all use TimeChart)

- [ ] **Step 6: Commit**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/lib/components/TimeChart.svelte
git commit -m "feat(chart): click-to-toggle series visibility in chart legend"
```

---

## Wave Mapping for Cyber Factory

These tasks can be parallelized as follows:

**Wave 1 (2 workers):**
- Worker A (Backend, Opus): Task 1 + Task 2 — model, migration, API, status serialization
- Worker B (Frontend, Sonnet): Task 3 — types, visibility helper, patch API

**Wave 2 (3 workers, after Wave 1):**
- Worker C (Frontend, Sonnet): Task 4 — Settings UI
- Worker D (Frontend, Sonnet): Task 6 — TimeRangeSlider component + Overview bugfix
- Worker E (Frontend, Sonnet): Task 8 — Chart legend toggle

**Wave 3 (2 workers, after Wave 2):**
- Worker F (Frontend, Sonnet): Task 5 — apply visibility filter to all views (needs Task 3 + 4)
- Worker G (Frontend, Sonnet): Task 7 — add slider to remaining views (needs Task 6)
