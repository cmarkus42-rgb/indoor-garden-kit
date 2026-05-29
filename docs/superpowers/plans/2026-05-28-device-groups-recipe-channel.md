# Device Groups + Recipe Channel Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a DeviceGroup model + CRUD API to the backend, expose group management inline on the Devices page, and replace the recipe channel freetext prompt() with a groups-aware dropdown.

**Architecture:** Backend first (SQLModel model -> Alembic migration -> FastAPI router -> register in app), then frontend (types + API helpers -> Devices page group section -> recipe channel picker). Three separate commits: backend, group management UI, recipe channel selection.

**Tech Stack:** Python 3.14 / FastAPI / SQLModel / Alembic / httpx + pytest-asyncio (backend); SvelteKit 5 runes / TypeScript (frontend)

**Repos:**
- Backend: `/Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit`
- Frontend (this repo): `packages/grow-dashboard/`

---

## File Map

**Create (backend):**
- `src/orchestrator/db/migrations/versions/003_device_groups.py`
- `src/orchestrator/api/groups.py`
- `tests/test_api_groups.py`

**Modify (backend):**
- `src/orchestrator/db/models.py` — append `DeviceGroup` class
- `src/orchestrator/app.py` — import + register `groups_router`
- `tests/conftest.py` — add `DeviceGroup` to model imports; add `app_client` fixture

**Modify (frontend, indoor-garden-kit):**
- `packages/grow-dashboard/src/lib/types.ts` — add `DeviceGroup`, `GroupsResponse`
- `packages/grow-dashboard/src/lib/api.ts` — handle 204 in `request()`; add group CRUD helpers
- `packages/grow-dashboard/src/routes/devices/+page.svelte` — group management section
- `packages/grow-dashboard/src/routes/recipes/[name]/+page.svelte` — channel picker

---

## Task 1: Add DeviceGroup model

**Files:**
- Modify: `src/orchestrator/db/models.py` (in cipher-grow-kit)

- [ ] **Step 1: Append DeviceGroup class to `models.py`**

All needed imports (`uuid`, `Field`, `SQLModel`, `Column`, `JSON`) are already at the top of the file. Append after the `Alert` class (after line 80):

```python
class DeviceGroup(SQLModel, table=True):
    __tablename__ = "device_groups"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    name: str = Field(index=True)
    category: str  # "light" | "irrigation" | "climate" | "other"
    device_ids: list[str] = Field(default_factory=list, sa_column=Column(JSON, default=[]))
```

---

## Task 2: Add Alembic migration 003

**Files:**
- Create: `src/orchestrator/db/migrations/versions/003_device_groups.py` (in cipher-grow-kit)

- [ ] **Step 1: Create the migration file**

```python
"""Add device_groups table

Revision ID: 003
Revises: 002
Create Date: 2026-05-28
"""

from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_groups",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, index=True),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("device_ids", sa.JSON(), server_default="[]"),
    )


def downgrade() -> None:
    op.drop_table("device_groups")
```

---

## Task 3: Update conftest + write failing API tests

**Files:**
- Modify: `tests/conftest.py` (in cipher-grow-kit)
- Create: `tests/test_api_groups.py` (in cipher-grow-kit)

- [ ] **Step 1: Add `DeviceGroup` to model import and add `app_client` fixture in `conftest.py`**

Change the import on line 12:
```python
from orchestrator.db.models import (  # noqa: F401
    Alert, Device, DeviceGroup, IrrigationEvent, LightSchedule, SensorReading,
)
```

Append the following fixture at the end of `conftest.py`:
```python
@pytest_asyncio.fixture
async def app_client(engine):
    """FastAPI AsyncClient with session dependency overridden to use in-memory SQLite."""
    from httpx import AsyncClient, ASGITransport
    from orchestrator.app import create_app
    from orchestrator.api.deps import get_session

    app = create_app(testing=True)

    async def override_session():
        async with AsyncSession(engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_session

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()
```

- [ ] **Step 2: Create `tests/test_api_groups.py`**

```python
from __future__ import annotations

import uuid

import pytest


async def test_list_groups_empty(app_client):
    res = await app_client.get("/api/groups")
    assert res.status_code == 200
    assert res.json() == {"groups": []}


async def test_create_group(app_client):
    body = {"name": "Main Light", "category": "light", "device_ids": ["uuid-1", "uuid-2"]}
    res = await app_client.post("/api/groups", json=body)
    assert res.status_code == 201
    data = res.json()
    assert data["name"] == "Main Light"
    assert data["category"] == "light"
    assert data["device_ids"] == ["uuid-1", "uuid-2"]
    assert "id" in data


async def test_create_group_default_empty_device_ids(app_client):
    res = await app_client.post("/api/groups", json={"name": "Climate Zone", "category": "climate"})
    assert res.status_code == 201
    assert res.json()["device_ids"] == []


async def test_list_groups_after_create(app_client):
    await app_client.post("/api/groups", json={"name": "Lights", "category": "light", "device_ids": []})
    res = await app_client.get("/api/groups")
    assert res.status_code == 200
    groups = res.json()["groups"]
    assert len(groups) == 1
    assert groups[0]["name"] == "Lights"
    assert groups[0]["category"] == "light"


async def test_update_group(app_client):
    create_res = await app_client.post(
        "/api/groups", json={"name": "Old Name", "category": "light", "device_ids": []}
    )
    group_id = create_res.json()["id"]

    res = await app_client.put(
        f"/api/groups/{group_id}",
        json={"name": "New Name", "category": "irrigation", "device_ids": ["uuid-x"]},
    )
    assert res.status_code == 200
    data = res.json()
    assert data["name"] == "New Name"
    assert data["category"] == "irrigation"
    assert data["device_ids"] == ["uuid-x"]


async def test_update_group_not_found(app_client):
    fake_id = str(uuid.uuid4())
    res = await app_client.put(
        f"/api/groups/{fake_id}",
        json={"name": "x", "category": "other", "device_ids": []},
    )
    assert res.status_code == 404


async def test_delete_group(app_client):
    create_res = await app_client.post(
        "/api/groups", json={"name": "To Delete", "category": "other", "device_ids": []}
    )
    group_id = create_res.json()["id"]

    del_res = await app_client.delete(f"/api/groups/{group_id}")
    assert del_res.status_code == 204

    list_res = await app_client.get("/api/groups")
    assert list_res.json() == {"groups": []}


async def test_delete_group_not_found(app_client):
    fake_id = str(uuid.uuid4())
    res = await app_client.delete(f"/api/groups/{fake_id}")
    assert res.status_code == 404
```

- [ ] **Step 3: Run tests to confirm they fail (router not yet registered)**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
source .venv/bin/activate
pytest tests/test_api_groups.py -v
```

Expected: All 8 tests FAIL — HTTP 404 (endpoint not found) or import error.

---

## Task 4: Implement groups API router

**Files:**
- Create: `src/orchestrator/api/groups.py` (in cipher-grow-kit)

- [ ] **Step 1: Create `src/orchestrator/api/groups.py`**

```python
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from orchestrator.api.deps import get_session
from orchestrator.db.models import DeviceGroup

router = APIRouter(prefix="/api")


class GroupBody(BaseModel):
    name: str
    category: str
    device_ids: list[str] = []


def _group_dict(g: DeviceGroup) -> dict:
    return {
        "id": str(g.id),
        "name": g.name,
        "category": g.category,
        "device_ids": g.device_ids,
    }


@router.get("/groups")
async def list_groups(session: AsyncSession = Depends(get_session)):
    result = await session.exec(select(DeviceGroup))
    return {"groups": [_group_dict(g) for g in result.all()]}


@router.post("/groups", status_code=201)
async def create_group(body: GroupBody, session: AsyncSession = Depends(get_session)):
    group = DeviceGroup(name=body.name, category=body.category, device_ids=body.device_ids)
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _group_dict(group)


@router.put("/groups/{group_id}")
async def update_group(
    group_id: uuid.UUID,
    body: GroupBody,
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    group.name = body.name
    group.category = body.category
    group.device_ids = body.device_ids
    session.add(group)
    await session.commit()
    await session.refresh(group)
    return _group_dict(group)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(
    group_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
):
    group = await session.get(DeviceGroup, group_id)
    if not group:
        raise HTTPException(status_code=404, detail="Group not found")
    await session.delete(group)
    await session.commit()
```

---

## Task 5: Register router, run tests, commit backend

**Files:**
- Modify: `src/orchestrator/app.py` (in cipher-grow-kit)

- [ ] **Step 1: Import groups router in `app.py`**

Add after the `recipes_router` import line (around line 19):
```python
from orchestrator.api.groups import router as groups_router
```

- [ ] **Step 2: Register router in `create_app()`**

Add after `app.include_router(recipes_router)` (around line 229):
```python
app.include_router(groups_router)
```

- [ ] **Step 3: Run all backend tests**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
source .venv/bin/activate
pytest tests/ -v
```

Expected: All tests PASS. The 8 new group tests plus existing model tests all green.

- [ ] **Step 4: Commit backend**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/cipher-grow-kit
git add src/orchestrator/db/models.py \
        src/orchestrator/db/migrations/versions/003_device_groups.py \
        src/orchestrator/api/groups.py \
        src/orchestrator/app.py \
        tests/conftest.py \
        tests/test_api_groups.py
git commit -m "feat(backend): DeviceGroup model + CRUD API + migration 003 (REQ-DASH-004)"
```

---

## Task 6: Frontend types + API helpers

**Files:**
- Modify: `packages/grow-dashboard/src/lib/types.ts`
- Modify: `packages/grow-dashboard/src/lib/api.ts`

All commands from here run in the `indoor-garden-kit` repo root.

- [ ] **Step 1: Add `DeviceGroup` and `GroupsResponse` to `types.ts`**

Append after the `QueueResponse` interface (after line 130):

```typescript
export interface DeviceGroup {
  id: string;
  name: string;
  category: 'light' | 'irrigation' | 'climate' | 'other';
  device_ids: string[];
}

export interface GroupsResponse {
  groups: DeviceGroup[];
}
```

- [ ] **Step 2: Update `request()` in `api.ts` to handle 204 No Content**

The DELETE endpoint returns 204 with no body. Calling `res.json()` on a 204 response throws. Replace the `request` function (lines 7-20) with:

```typescript
async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const opts: RequestInit = {
    method,
    headers: { 'Content-Type': 'application/json' }
  };
  if (body !== undefined) {
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(path, opts);
  if (!res.ok) {
    throw new ApiError(res.status, `${method} ${path}: ${res.status}`);
  }
  if (res.status === 204) return null as T;
  return res.json();
}
```

- [ ] **Step 3: Add group CRUD helpers at the end of `api.ts`**

```typescript
import type { DeviceGroup, GroupsResponse } from '$lib/types.js';

export function getGroups(): Promise<GroupsResponse> {
  return get<GroupsResponse>('/api/groups');
}

export function createGroup(body: {
  name: string;
  category: string;
  device_ids: string[];
}): Promise<DeviceGroup> {
  return post<DeviceGroup>('/api/groups', body);
}

export function updateGroup(
  id: string,
  body: { name: string; category: string; device_ids: string[] }
): Promise<DeviceGroup> {
  return put<DeviceGroup>(`/api/groups/${id}`, body);
}

export function deleteGroup(id: string): Promise<void> {
  return del<void>(`/api/groups/${id}`);
}
```

---

## Task 7: Group management section in Devices page

**Files:**
- Modify: `packages/grow-dashboard/src/routes/devices/+page.svelte`

- [ ] **Step 1: Update imports in the script block**

Change:
```typescript
import { get, put, post } from '$lib/api.js';
```
to:
```typescript
import { get, put, post, getGroups, createGroup, updateGroup, deleteGroup } from '$lib/api.js';
```

Add `DeviceGroup` to the type imports block:
```typescript
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
```

- [ ] **Step 2: Add group state variables**

After the `let openAlerts` derived line, add:
```typescript
// ── Group management ────────────────────────────────────────────────────────
let groups = $state<DeviceGroup[]>([]);
// groupEditId: null = closed, 'new' = creating, <uuid string> = editing existing
let groupEditId = $state<string | null>(null);
let groupForm = $state<{ name: string; category: DeviceGroup['category']; device_ids: string[] }>({
  name: '',
  category: 'light',
  device_ids: []
});
```

- [ ] **Step 3: Add group CRUD functions**

Add after the `clearAllAlerts` function:
```typescript
// ── Group management ────────────────────────────────────────────────────────
async function loadGroups() {
  try {
    const res = await getGroups();
    groups = res.groups;
  } catch { /* ignore */ }
}

function startNewGroup() {
  groupEditId = 'new';
  groupForm = { name: '', category: 'light', device_ids: [] };
}

function startEditGroup(g: DeviceGroup) {
  groupEditId = g.id;
  groupForm = { name: g.name, category: g.category, device_ids: [...g.device_ids] };
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
  const body = { name: groupForm.name.trim(), category: groupForm.category, device_ids: groupForm.device_ids };
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
```

- [ ] **Step 4: Call `loadGroups()` from the `load()` function**

Inside `async function load()`, append at the end (before the closing brace):
```typescript
    await loadGroups();
```

- [ ] **Step 5: Add the Groups section to the template**

After the closing `{/each}` of the `GROUP_ORDER` loop (just before `</div><!-- .devices-panel -->`), add:

```svelte
      <!-- ── Groups ──────────────────────────────────────────────────────── -->
      <section class="device-group">
        <div class="group-header-row">
          <h2 class="group-header">Groups</h2>
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
            <div class="group-row">
              <span class="group-row-name">{g.name}</span>
              <span class="group-category-chip group-category-chip--{g.category}">{g.category}</span>
              <span class="group-row-count">{g.device_ids.length} device{g.device_ids.length === 1 ? '' : 's'}</span>
              <button class="btn-group-action" onclick={() => startEditGroup(g)}>Edit</button>
              <button class="btn-group-action btn-group-delete" onclick={() => removeGroup(g.id)}>Delete</button>
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
      </section>
```

- [ ] **Step 6: Add styles for the Groups section**

Append inside the `<style>` block (before `</style>`):

```css
  /* ── Groups section ──────────────────────────────────────────────────────── */
  .group-header-row {
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
```

- [ ] **Step 7: Commit frontend group management**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/lib/types.ts \
        packages/grow-dashboard/src/lib/api.ts \
        packages/grow-dashboard/src/routes/devices/+page.svelte
git commit -m "feat(dashboard): device group management UI + API helpers (REQ-DASH-004)"
```

---

## Task 8: Recipe channel picker (REQ-DASH-009)

**Files:**
- Modify: `packages/grow-dashboard/src/routes/recipes/[name]/+page.svelte`

- [ ] **Step 1: Update imports**

Change:
```typescript
import { get, put } from '$lib/api.js';
```
to:
```typescript
import { get, put, getGroups } from '$lib/api.js';
```

Add `DeviceGroup` to the type imports:
```typescript
import type { RecipeData, ChannelRule, DeviceGroup } from '$lib/types.js';
```

- [ ] **Step 2: Add picker state variables**

After `let copied = $state(false)`, add:
```typescript
let lightGroups = $state<DeviceGroup[]>([]);
let channelPickerOpen = $state(false);
let channelPickerValue = $state('');
```

- [ ] **Step 3: Load light groups in `load()`**

In the existing `load()` function, append at the end (before the closing brace):
```typescript
  try {
    const groupsRes = await getGroups();
    lightGroups = groupsRes.groups.filter(g => g.category === 'light');
    if (lightGroups.length > 0) channelPickerValue = lightGroups[0].name;
  } catch { /* no groups yet */ }
```

- [ ] **Step 4: Replace `addChannel()` with picker-aware functions**

Remove the current `addChannel()` function and replace with:
```typescript
function openChannelPicker() {
  if (!recipe) return;
  if (lightGroups.length === 0) {
    // No groups defined yet — fall back to prompt
    const ch = prompt('Channel name:');
    if (!ch) return;
    if (!(ch in recipe.channels)) {
      recipe.channels[ch] = { rule: 'before_on', offset_min: 15, duration_min: 30 };
      recipe = { ...recipe };
    }
    return;
  }
  channelPickerOpen = true;
  channelPickerValue = lightGroups[0].name;
}

function confirmChannelPick() {
  if (!recipe) return;
  let name = channelPickerValue;
  if (name === '__custom__') {
    name = prompt('Channel name:') ?? '';
  }
  channelPickerOpen = false;
  if (!name) return;
  if (!(name in recipe.channels)) {
    recipe.channels[name] = { rule: 'before_on', offset_min: 15, duration_min: 30 };
    recipe = { ...recipe };
  }
}
```

- [ ] **Step 5: Replace the "+ Add" button in the channels section header**

Find (around line 210):
```svelte
<div class="section-header">
  <span class="section-label">CHANNELS</span>
  <button class="btn-ghost-sm" onclick={addChannel}>+ Add</button>
</div>
```

Replace with:
```svelte
<div class="section-header">
  <span class="section-label">CHANNELS</span>
  {#if channelPickerOpen}
    <div class="channel-picker">
      <select class="input-select-sm" bind:value={channelPickerValue}>
        {#each lightGroups as g (g.id)}
          <option value={g.name}>{g.name}</option>
        {/each}
        <option value="__custom__">Custom...</option>
      </select>
      <button class="btn-ghost-sm" onclick={confirmChannelPick}>Add</button>
      <button class="btn-ghost-sm" onclick={() => (channelPickerOpen = false)}>Cancel</button>
    </div>
  {:else}
    <button class="btn-ghost-sm" onclick={openChannelPicker}>+ Add</button>
  {/if}
</div>
```

- [ ] **Step 6: Add `.channel-picker` style**

Append inside the `<style>` block (before `</style>`):
```css
  /* ── Channel picker ── */
  .channel-picker {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }
```

- [ ] **Step 7: Commit recipe channel selection**

```bash
cd /Users/Shared/Nextcloud/Claude/CIPHER-MUX/projects/indoor-garden-kit
git add packages/grow-dashboard/src/routes/recipes/[name]/+page.svelte
git commit -m "feat(dashboard): recipe channel picker uses device groups (REQ-DASH-009)"
```

---

## Self-Review

**Spec coverage:**
- REQ-DASH-004 backend (DeviceGroup model + migration + CRUD API): Tasks 1-5
- REQ-DASH-004 frontend (group management section in Devices page): Task 7
- REQ-DASH-009 (channel selection dropdown in Recipe editor): Task 8
- Tests for all 4 CRUD endpoints (list, create, update, delete) + 404 cases: Task 3
- Backward compat for freetext channel names: confirmed — channel keys are plain dict keys, existing ones render unchanged

**Placeholder scan:** No TBDs, no "similar to Task N", all code blocks complete.

**Type consistency:**
- `DeviceGroup` defined in Task 6 Step 1; used as `DeviceGroup[]` in Tasks 7 and 8
- `GroupBody` (backend) fields `name/category/device_ids` match `_group_dict()` output
- `getGroups()` returns `GroupsResponse` with `.groups: DeviceGroup[]`
- `groupForm.category` typed as `DeviceGroup['category']` to match the union
- `channelPickerValue` and `openChannelPicker`/`confirmChannelPick` consistent throughout Task 8
- `request()` 204 fix in Task 6 Step 2 covers `deleteGroup` in Task 7
