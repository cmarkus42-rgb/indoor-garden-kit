# Device Visibility & Dashboard Control

**Date:** 2026-05-29
**Scope:** Backend (cipher-grow-kit) + Frontend (indoor-garden-kit/packages/grow-dashboard)

## Problem

All 29 devices are shown in every view. Not all devices are always in use. Users need:
- A way to deactivate unused devices globally
- Per-view control over which devices/sensors appear
- Interactive chart line toggling
- A working time-range slider across all chart views

## Design

### 1. Backend — Device Model Extension

Add two columns to `Device` (migration 004):

```python
enabled: bool = Field(default=True)
view_visibility: dict = Field(default_factory=dict, sa_column=Column(JSON, default={}))
```

`enabled` is the global kill-switch. A disabled device is excluded from all views, polling continues unchanged.

`view_visibility` is a JSON map of view names to booleans:
```json
{"overview": true, "investigate": false, "energy": true, "ventilation": true, "recipes": true}
```

Missing keys default to `true` (visible). Only explicit `false` hides a device from a view.

Valid view keys: `overview`, `investigate`, `energy`, `ventilation`, `recipes`.

### 2. Backend — API

**`PATCH /api/device/{id}/config`**

Request body:
```json
{
  "enabled": false,
  "view_visibility": {"overview": false, "investigate": true}
}
```

Both fields optional. `view_visibility` merges with existing values (does not replace the whole map).

Response: updated `Device` object.

**`GET /api/status`** — already returns all devices. Add `enabled` and `view_visibility` to the device serialization. No new endpoint needed.

### 3. Frontend — Device Interface

Extend `Device` in `src/lib/types.ts`:
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

### 4. Frontend — Visibility Filter

Shared helper in `src/lib/visibility.ts`:
```typescript
export function visibleDevices(devices: Device[], view: string): Device[] {
  return devices.filter(d => d.enabled && d.view_visibility[view] !== false);
}
```

Each view calls `visibleDevices(status.devices, 'overview')` instead of using `status.devices` directly.

Affected views:
- `src/routes/+page.svelte` (overview) — `climateDevices`, `soilDevices` filters
- `src/routes/investigate/+page.svelte` — device list for metric groups
- `src/routes/energy/+page.svelte` — plug filter
- `src/routes/ventilation/+page.svelte` — controller list
- `src/routes/recipes/[name]/+page.svelte` — group device lists

### 5. Frontend — Settings UI

Extend the device list in `src/routes/settings/+page.svelte`:

Each device row gets:
- **Enable/Disable toggle** — calls `PATCH /api/device/{id}/config` with `{enabled: bool}`
- **Expandable section** — five checkboxes (Overview, Investigate, Energy, Ventilation, Recipes)
- Toggling a checkbox calls `PATCH /api/device/{id}/config` with `{view_visibility: {viewName: bool}}`
- Disabled devices show greyed out, checkboxes disabled

### 6. Frontend — Chart Line Toggle

All views using `TimeChart` get interactive series toggling:
- Click on a sensor label/legend item toggles that series line visibility
- Implementation: `uPlot` series `show` property toggled on click
- State is local (not persisted) — resets on page load
- Visual feedback: hidden series label gets reduced opacity

Affected components:
- `src/lib/components/TimeChart.svelte` — add click handler on legend items, toggle `series[i].show`
- All views using TimeChart benefit automatically

### 7. Time-Range Slider — Bugfix + Rollout

**Bugfix (Overview):**
- Default `rangeStep` from `0` ("Last hour") to `4` ("Last 24 hours") — avoids empty charts when no data in the last hour

**Extract component:**
- New `src/lib/components/TimeRangeSlider.svelte`
- Props: `steps` (LOG_STEPS array), `value` (bindable rangeStep)
- Emits filtered cutoff timestamp
- Move `filterByRange` into the component or export as utility

**Rollout to all chart views:**
- `src/routes/+page.svelte` — replace inline slider with component
- `src/routes/investigate/+page.svelte` — add slider
- `src/routes/energy/+page.svelte` — add slider
- `src/routes/ventilation/+page.svelte` — add slider

### 8. Migration

Migration 004: `add_device_visibility_columns`
- `ALTER TABLE devices ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT TRUE`
- `ALTER TABLE devices ADD COLUMN view_visibility JSON NOT NULL DEFAULT '{}'`

All existing devices default to enabled + visible everywhere (no behavioral change on deploy).

## Files Changed

### cipher-grow-kit (Backend)
| File | Change |
|------|--------|
| `src/orchestrator/db/models.py` | Add `enabled`, `view_visibility` to Device |
| `src/orchestrator/db/migrations/versions/004_*.py` | New migration |
| `src/orchestrator/api/device.py` | Add `PATCH /api/device/{id}/config` |
| `src/orchestrator/app.py` | Include `enabled`, `view_visibility` in status serialization |

### indoor-garden-kit (Frontend)
| File | Change |
|------|--------|
| `src/lib/types.ts` | Extend Device interface |
| `src/lib/visibility.ts` | New: `visibleDevices()` helper |
| `src/lib/components/TimeRangeSlider.svelte` | New: extracted slider component |
| `src/lib/components/TimeChart.svelte` | Add legend click → series toggle |
| `src/routes/+page.svelte` | Use `visibleDevices()`, replace inline slider |
| `src/routes/investigate/+page.svelte` | Use `visibleDevices()`, add slider |
| `src/routes/energy/+page.svelte` | Use `visibleDevices()`, add slider |
| `src/routes/ventilation/+page.svelte` | Use `visibleDevices()`, add slider |
| `src/routes/recipes/[name]/+page.svelte` | Use `visibleDevices()` |
| `src/routes/settings/+page.svelte` | Enable toggle + view visibility checkboxes |

## Risks

- Migration is additive (new columns with defaults) — safe, no data loss
- `view_visibility` merge semantics: PATCH merges, not replaces — frontend must send only changed keys
- Chart toggle is uPlot-native (`series.show`) — no custom canvas logic needed
- Time slider extraction is a refactor of existing code — no new logic
