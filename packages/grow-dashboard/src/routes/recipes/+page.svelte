<script lang="ts">
  import { get, del, put } from '$lib/api.js';
  import type { RecipesResponse, RecipeSummary, RecipeData, DayPlanResponse, QueueEntry, QueueResponse } from '$lib/types.js';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import Chip from '$lib/components/Chip.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  // ── Catalog state ──
  let recipes = $state<RecipeSummary[]>([]);
  let recipeDetails = $state<Record<string, RecipeData>>({});
  let activeRecipeName = $state<string | null>(null);

  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  let nowMin = $state(getNowMin());

  // ── Plan state ──
  let queue = $state<QueueEntry[]>([]);
  let today = $state<DayPlanResponse | null>(null);
  let saving = $state(false);
  let dirty = $state(false);
  let error = $state('');

  // ── Duration editor state ──
  let editingIdx = $state<number | null>(null);
  let editMonths = $state(0);
  let editWeeks = $state(0);
  let editDays = $state(0);
  let editExact = $state(false);
  let editDate = $state('');

  // ── Drag state ──
  let dragIdx = $state<number | null>(null);
  let dragOverIdx = $state<number | null>(null);

  // ── Import state ──
  let showImport = $state(false);
  let importJson = $state('');
  let importError = $state('');
  let fileInput: HTMLInputElement;

  // ── Palette ──
  const PALETTE = [
    'oklch(72% 0.18 145)',
    'oklch(68% 0.20 280)',
    'oklch(75% 0.18 55)',
    'oklch(70% 0.22 330)',
    'oklch(78% 0.14 200)',
    'oklch(72% 0.20 25)',
  ];

  function recipeColor(name: string): string {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
    return PALETTE[Math.abs(h) % PALETTE.length];
  }

  // ── Computed: which entry is active today ──
  let activeEntryIdx = $derived.by(() => {
    const now = new Date();
    let start = new Date();
    for (let i = 0; i < queue.length; i++) {
      const e = queue[i];
      if (e.recipe) {
        if (!e.until) return i; // open-end = currently active
        const end = new Date(e.until);
        if (now < end) return i;
        start = end;
      } else if (e.transition_to && e.days) {
        const end = new Date(start.getTime() + e.days * 86400000);
        if (now < end) return i;
        start = end;
      }
    }
    return queue.length > 0 ? queue.length - 1 : -1;
  });

  // ── Load functions ──
  async function loadCatalog() {
    const [res, dayPlan] = await Promise.all([
      get<RecipesResponse>('/api/recipes'),
      get<DayPlanResponse>('/api/schedule/today').catch(() => null),
    ]);
    recipes = res.recipes;
    activeRecipeName = dayPlan?.recipe_name ?? null;
    today = dayPlan;
    const details = await Promise.all(
      recipes.map(r =>
        get<RecipeData>(`/api/recipes/${encodeURIComponent(r.name)}`).catch(() => null)
      )
    );
    const map: Record<string, RecipeData> = {};
    for (const d of details) if (d) map[d.name] = d;
    recipeDetails = map;
  }

  async function loadQueue() {
    try {
      const res = await get<QueueResponse>('/api/queue');
      queue = res.entries;
      dirty = false;
    } catch {
      queue = [];
    }
  }

  async function loadToday() {
    try {
      today = await get<DayPlanResponse>('/api/schedule/today');
    } catch {
      today = null;
    }
  }

  onMount(() => {
    loadCatalog();
    loadQueue();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  // ── Catalog actions ──
  async function handleNew() {
    const name = prompt('Recipe name:');
    if (!name) return;
    const data: RecipeData = {
      name,
      photoperiod: { on: '06:00', off: '00:00' },
      dimming: { sunrise_min: 30, sunset_min: 30, max_pct: 100, min_pct: 0 },
      channels: {},
    };
    await put(`/api/recipes/${encodeURIComponent(name)}`, data);
    goto(`/recipes/${encodeURIComponent(name)}`);
  }

  async function handleDelete(name: string, e: Event) {
    e.stopPropagation();
    if (!confirm(`Delete recipe "${name}"?`)) return;
    await del(`/api/recipes/${encodeURIComponent(name)}`);
    await loadCatalog();
  }

  async function handleClone(name: string, e: Event) {
    e.stopPropagation();
    const data = await get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`);
    const cloneName = `${data.name} (Copy)`;
    const cloned: RecipeData = { ...data, name: cloneName };
    await put(`/api/recipes/${encodeURIComponent(cloneName)}`, cloned);
    await loadCatalog();
  }

  async function handleFileChange(e: Event) {
    const file = (e.target as HTMLInputElement).files?.[0];
    if (!file) return;
    importJson = await file.text();
    showImport = true;
    (e.target as HTMLInputElement).value = '';
  }

  async function handleImport() {
    importError = '';
    try {
      const data = JSON.parse(importJson) as RecipeData;
      await put(`/api/recipes/${encodeURIComponent(data.name)}`, data);
      importJson = '';
      showImport = false;
      await loadCatalog();
    } catch (e) {
      importError = `Invalid JSON: ${e}`;
    }
  }

  // ── Plan actions ──
  function addToPlan(name: string) {
    queue = [...queue, { recipe: name, until: undefined }];
    dirty = true;
  }

  function insertTransition(idx: number) {
    // Insert a transition between idx and idx+1
    const next = queue[idx + 1];
    const targetName = next?.recipe ?? next?.transition_to ?? '';
    const entry: QueueEntry = { transition_to: targetName, days: 7 };
    queue = [...queue.slice(0, idx + 1), entry, ...queue.slice(idx + 1)];
    dirty = true;
  }

  function removeEntry(idx: number) {
    queue = queue.filter((_, i) => i !== idx);
    editingIdx = null;
    dirty = true;
  }

  function moveEntry(from: number, to: number) {
    if (from === to) return;
    const arr = [...queue];
    const [item] = arr.splice(from, 1);
    arr.splice(to, 0, item);
    queue = arr;
    dirty = true;
  }

  function openDurationEditor(idx: number) {
    const e = queue[idx];
    editingIdx = idx;
    editExact = false;
    editDate = '';
    editMonths = 0;
    editWeeks = 0;
    editDays = 0;

    if (e.recipe && e.until) {
      editExact = true;
      editDate = e.until;
    } else if (e.transition_to && e.days) {
      editDays = e.days;
    }
  }

  function applyDuration() {
    if (editingIdx == null) return;
    const e = { ...queue[editingIdx] };

    if (e.transition_to) {
      // Transition: set days from combined inputs
      const total = editMonths * 30 + editWeeks * 7 + editDays;
      e.days = Math.max(1, total);
    } else if (e.recipe) {
      if (editExact && editDate) {
        e.until = editDate;
      } else {
        // Compute until from start + duration
        const total = editMonths * 30 + editWeeks * 7 + editDays;
        if (total > 0) {
          const startDate = computeEntryStart(editingIdx);
          const end = new Date(startDate.getTime() + total * 86400000);
          e.until = end.toISOString().slice(0, 10);
        } else {
          e.until = undefined;
        }
      }
    }

    queue = queue.map((q, i) => i === editingIdx ? e : q);
    editingIdx = null;
    dirty = true;
  }

  function computeEntryStart(idx: number): Date {
    let d = new Date();
    for (let i = 0; i < idx; i++) {
      const e = queue[i];
      if (e.recipe && e.until) {
        d = new Date(e.until);
      } else if (e.transition_to && e.days) {
        d = new Date(d.getTime() + e.days * 86400000);
      }
    }
    return d;
  }

  function entryDurationLabel(e: QueueEntry, idx: number): string {
    if (e.transition_to && e.days) return `${e.days}d`;
    if (e.recipe && e.until) {
      const start = computeEntryStart(idx);
      const end = new Date(e.until);
      const days = Math.max(0, Math.ceil((end.getTime() - start.getTime()) / 86400000));
      return `${days}d`;
    }
    return '';
  }

  async function saveQueue() {
    saving = true;
    error = '';
    try {
      // Set last recipe entry to until: null
      const entries = queue.map((e, i) => {
        if (e.recipe && i === queue.length - 1) return { recipe: e.recipe, until: null };
        if (e.recipe) return { recipe: e.recipe, until: e.until || null };
        return { transition_to: e.transition_to, days: e.days };
      });
      await put('/api/queue', { entries });
      dirty = false;
      await loadToday();
    } catch (e) {
      error = `Save failed: ${e}`;
    } finally {
      saving = false;
    }
  }

  // ── Drag handlers for plan reorder ──
  function onPlanDragStart(idx: number, e: DragEvent) {
    dragIdx = idx;
    e.dataTransfer!.effectAllowed = 'move';
    e.dataTransfer!.setData('text/plain', String(idx));
  }

  function onPlanDragOver(idx: number, e: DragEvent) {
    e.preventDefault();
    e.dataTransfer!.dropEffect = 'move';
    dragOverIdx = idx;
  }

  function onPlanDrop(idx: number, e: DragEvent) {
    e.preventDefault();
    if (dragIdx != null && dragIdx !== idx) {
      moveEntry(dragIdx, idx);
    }
    dragIdx = null;
    dragOverIdx = null;
  }

  function onPlanDragEnd() {
    dragIdx = null;
    dragOverIdx = null;
  }

  // ── Drag from catalog ──
  function onCatalogDragStart(name: string, e: DragEvent) {
    e.dataTransfer!.effectAllowed = 'copy';
    e.dataTransfer!.setData('application/x-recipe', name);
  }

  function onPlanAreaDragOver(e: DragEvent) {
    if (e.dataTransfer!.types.includes('application/x-recipe')) {
      e.preventDefault();
      e.dataTransfer!.dropEffect = 'copy';
    }
  }

  function onPlanAreaDrop(e: DragEvent) {
    const name = e.dataTransfer!.getData('application/x-recipe');
    if (name) {
      e.preventDefault();
      addToPlan(name);
    }
  }

  function fmtMinutes(min: number): string {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }
</script>

<div class="page">
  <!-- ── Header ── -->
  <div class="page-header">
    <h1 class="page-title">RECIPES</h1>
    <div class="header-actions">
      <button class="btn-ghost" onclick={handleNew}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <line x1="6.5" y1="1" x2="6.5" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          <line x1="1" y1="6.5" x2="12" y2="6.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
        </svg>
        New Recipe
      </button>
      <button class="btn-ghost" onclick={() => fileInput.click()}>
        <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
          <path d="M6.5 1.5v6M4 5.5l2.5 2.5L9 5.5M1.5 10.5h10" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        JSON Import
      </button>
      <input
        bind:this={fileInput}
        type="file"
        accept=".json,application/json"
        class="file-hidden"
        onchange={handleFileChange}
      />
    </div>
  </div>

  <!-- ── Import Panel ── -->
  {#if showImport}
    <div class="import-panel">
      <div class="import-header">
        <span class="section-label">JSON IMPORT</span>
        <button class="btn-icon" onclick={() => { showImport = false; importJson = ''; importError = ''; }} aria-label="Close">
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <line x1="2.5" y1="2.5" x2="10.5" y2="10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="10.5" y1="2.5" x2="2.5" y2="10.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>
      <textarea
        class="json-area"
        bind:value={importJson}
        rows="8"
        placeholder="Paste recipe JSON..."
      ></textarea>
      {#if importError}
        <p class="import-error">{importError}</p>
      {/if}
      <div class="import-actions">
        <button class="btn-accent" onclick={handleImport} disabled={!importJson.trim()}>Import</button>
      </div>
    </div>
  {/if}

  <!-- ── Two-Column Layout ── -->
  <div class="columns">
    <!-- ── LEFT: Recipe Catalog ── -->
    <div class="col-catalog">
      {#if recipes.length === 0}
        <div class="empty-state">
          <span class="mono-label">NO RECIPES</span>
        </div>
      {:else}
        <div class="recipe-grid">
          {#each recipes as r}
            {@const detail = recipeDetails[r.name]}
            {@const isActive = activeRecipeName === r.name}
            <div
              class="recipe-card"
              class:recipe-card--active={isActive}
              draggable="true"
              ondragstart={(e) => onCatalogDragStart(r.name, e)}
            >
              <a class="card-body" href="/recipes/{encodeURIComponent(r.name)}">
                <div class="card-top">
                  <div class="card-info">
                    <div class="card-name-row">
                      <h3 class="card-name">{r.name}</h3>
                      {#if isActive}
                        <span class="active-badge">ACTIVE</span>
                      {/if}
                    </div>
                    <div class="card-chips">
                      <Chip variant="light">{r.photoperiod}</Chip>
                      <Chip>{r.channels} ch</Chip>
                    </div>
                  </div>
                  <div class="card-ring">
                    {#if detail}
                      <PolarRing recipe={detail} nowMin={nowMin} size="mini" />
                    {:else}
                      <div class="ring-placeholder"></div>
                    {/if}
                  </div>
                </div>
              </a>
              <div class="card-actions">
                <button class="btn-small btn-small--add" onclick={(e) => { e.stopPropagation(); addToPlan(r.name); }} title="Add to plan">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <line x1="5" y1="1" x2="5" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="1" y1="5" x2="9" y2="5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                  Plan
                </button>
                <button class="btn-small" onclick={(e) => handleClone(r.name, e)}>Clone</button>
                <button class="btn-small btn-small--danger" onclick={(e) => handleDelete(r.name, e)}>Delete</button>
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <!-- ── RIGHT: Grow Plan ── -->
    <div
      class="col-plan"
      ondragover={onPlanAreaDragOver}
      ondrop={onPlanAreaDrop}
    >
      <div class="plan-sticky">
        <div class="plan-header">
          <span class="plan-title">GROW PLAN</span>
          <div class="plan-header-actions">
            {#if error}
              <span class="plan-error">{error}</span>
            {/if}
            <button
              class="btn-accent btn-accent--sm"
              onclick={saveQueue}
              disabled={saving || !dirty}
            >
              {saving ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>

        <!-- ── Plan Entries ── -->
        <div class="plan-list">
          {#if queue.length === 0}
            <div class="plan-empty">
              <span class="mono-label">DROP OR ADD RECIPES</span>
            </div>
          {:else}
            {#each queue as entry, idx}
              <!-- Transition insert zone (between entries) -->
              {#if idx > 0 && !(entry.transition_to) && !(queue[idx - 1]?.transition_to)}
                <button
                  class="trans-insert"
                  onclick={() => insertTransition(idx - 1)}
                  title="Insert transition"
                >
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <line x1="5" y1="1" x2="5" y2="9" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                    <line x1="1" y1="5" x2="9" y2="5" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/>
                  </svg>
                  <span class="trans-insert-label">Transition</span>
                </button>
              {/if}

              <div
                class="plan-card"
                class:plan-card--recipe={!!entry.recipe}
                class:plan-card--transition={!!entry.transition_to}
                class:plan-card--active={idx === activeEntryIdx}
                class:plan-card--dragover={dragOverIdx === idx}
                style={entry.recipe ? `--card-accent: ${recipeColor(entry.recipe)}` : entry.transition_to ? `--card-accent: ${recipeColor(entry.transition_to)}` : ''}
                draggable="true"
                ondragstart={(e) => onPlanDragStart(idx, e)}
                ondragover={(e) => onPlanDragOver(idx, e)}
                ondrop={(e) => onPlanDrop(idx, e)}
                ondragend={onPlanDragEnd}
              >
                <!-- Today indicator -->
                {#if idx === activeEntryIdx}
                  <div class="today-mark">
                    <span class="today-dot"></span>
                    <span class="today-text">TODAY</span>
                  </div>
                {/if}

                <div class="plan-card-main" onclick={() => openDurationEditor(idx)}>
                  {#if entry.recipe}
                    <span class="plan-dot" style="background: {recipeColor(entry.recipe)}"></span>
                    <span class="plan-name">{entry.recipe}</span>
                    <span class="plan-dur">
                      {#if entry.until}
                        {entryDurationLabel(entry, idx)} &middot; until {entry.until}
                      {:else}
                        <span class="plan-open">open end</span>
                      {/if}
                    </span>
                  {:else if entry.transition_to}
                    <span class="plan-arrow">
                      <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                        <path d="M2 6h8M7 3l3 3-3 3" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                      </svg>
                    </span>
                    <span class="plan-name plan-name--trans">{entry.transition_to}</span>
                    <span class="plan-dur">{entry.days}d</span>
                  {/if}
                </div>

                <div class="plan-card-btns">
                  <button class="plan-btn-move" onclick={() => { if (idx > 0) moveEntry(idx, idx - 1); }} disabled={idx === 0} aria-label="Move up" title="Move up">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none"><path d="M1 5.5L4 2.5L7 5.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </button>
                  <button class="plan-btn-move" onclick={() => { if (idx < queue.length - 1) moveEntry(idx, idx + 1); }} disabled={idx === queue.length - 1} aria-label="Move down" title="Move down">
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none"><path d="M1 2.5L4 5.5L7 2.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/></svg>
                  </button>
                  <button class="plan-btn-del" onclick={() => removeEntry(idx)} aria-label="Remove">
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                      <line x1="2" y1="2" x2="8" y2="8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                      <line x1="8" y1="2" x2="2" y2="8" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
                    </svg>
                  </button>
                </div>

                <!-- Inline duration editor -->
                {#if editingIdx === idx}
                  <div class="dur-editor" onclick={(e) => e.stopPropagation()}>
                    {#if entry.recipe}
                      <div class="dur-toggle-row">
                        <label class="dur-toggle">
                          <input type="checkbox" bind:checked={editExact} />
                          <span>Exact date</span>
                        </label>
                      </div>
                      {#if editExact}
                        <input type="date" class="dur-date" bind:value={editDate} />
                      {:else}
                        <div class="dur-fields">
                          <label class="dur-field">
                            <input type="number" min="0" max="24" bind:value={editMonths} />
                            <span>mo</span>
                          </label>
                          <label class="dur-field">
                            <input type="number" min="0" max="52" bind:value={editWeeks} />
                            <span>wk</span>
                          </label>
                          <label class="dur-field">
                            <input type="number" min="0" max="365" bind:value={editDays} />
                            <span>d</span>
                          </label>
                        </div>
                      {/if}
                    {:else if entry.transition_to}
                      <div class="dur-fields">
                        <label class="dur-field">
                          <input type="number" min="0" max="24" bind:value={editMonths} />
                          <span>mo</span>
                        </label>
                        <label class="dur-field">
                          <input type="number" min="0" max="52" bind:value={editWeeks} />
                          <span>wk</span>
                        </label>
                        <label class="dur-field">
                          <input type="number" min="0" max="365" bind:value={editDays} />
                          <span>d</span>
                        </label>
                      </div>
                    {/if}
                    <div class="dur-actions">
                      <button class="dur-btn dur-btn--apply" onclick={applyDuration}>Apply</button>
                      <button class="dur-btn" onclick={() => editingIdx = null}>Cancel</button>
                    </div>
                  </div>
                {/if}
              </div>
            {/each}
          {/if}
        </div>

        <!-- ── Today Preview ── -->
        {#if today}
          <div class="today-preview">
            <div class="tp-head">
              <span class="tp-label">TODAY</span>
              <span class="tp-recipe">{today.recipe_name}</span>
              <span class="tp-date">{today.date}</span>
            </div>
            <div class="tp-grid">
              <div class="tp-kv">
                <span class="tp-k">PHOTO</span>
                <span class="tp-v">{fmtMinutes(today.main_on)}&ndash;{fmtMinutes(today.main_off)}</span>
              </div>
              <div class="tp-kv">
                <span class="tp-k">DIMMING</span>
                <span class="tp-v">
                  {today.dimming_curve.length ? `${today.dimming_curve[0].pct}%–${Math.max(...today.dimming_curve.map(d => d.pct))}%` : '—'}
                </span>
              </div>
            </div>
            {#if today.transition_progress != null}
              <div class="tp-trans">
                <span class="tp-k">TRANSITION</span>
                <div class="tp-bar-track">
                  <div class="tp-bar-fill" style="width: {today.transition_progress * 100}%"></div>
                </div>
                <span class="tp-pct">{Math.round(today.transition_progress * 100)}%</span>
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  </div>
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  /* ── Header ── */
  .page-header {
    display: flex;
    align-items: center;
    gap: var(--s-4);
  }

  .page-title {
    font: 600 var(--t-24) var(--font-mono);
    color: var(--ink-1);
    letter-spacing: 0.08em;
    margin: 0;
    flex: 1;
  }

  .header-actions {
    display: flex;
    gap: var(--s-2);
  }

  .file-hidden {
    position: absolute;
    opacity: 0;
    width: 0;
    height: 0;
    pointer-events: none;
  }

  /* ── Import panel ── */
  .import-panel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .import-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .json-area {
    width: 100%;
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    color: var(--ink-1);
    font: 400 var(--t-11) var(--font-mono);
    padding: var(--s-3);
    resize: vertical;
    box-sizing: border-box;
    letter-spacing: 0.02em;
    line-height: 1.6;
  }

  .json-area:focus { outline: none; border-color: var(--accent-line); }

  .import-error {
    font: 400 var(--t-11) var(--font-mono);
    color: var(--st-crit);
    margin: 0;
  }

  .import-actions { display: flex; justify-content: flex-end; }

  /* ── Two-Column Layout ── */
  .columns {
    display: grid;
    grid-template-columns: 3fr 2fr;
    gap: var(--s-4);
    align-items: start;
  }

  @media (max-width: 840px) {
    .columns {
      grid-template-columns: 1fr;
    }
  }

  /* ── LEFT: Catalog ── */
  .col-catalog {
    min-width: 0;
  }

  .recipe-grid {
    display: grid;
    grid-template-columns: repeat(2, 1fr);
    gap: var(--s-3);
  }

  @media (max-width: 640px) {
    .recipe-grid {
      grid-template-columns: 1fr;
    }
  }

  .recipe-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
    transition: border-color 0.15s, background 0.15s;
    display: flex;
    flex-direction: column;
    cursor: grab;
  }

  .recipe-card:hover {
    border-color: var(--accent);
    background: var(--bg-2);
  }

  .recipe-card--active {
    border-color: var(--accent);
    box-shadow: 0 0 0 1px var(--accent);
  }

  .card-body {
    display: block;
    padding: var(--s-3);
    text-decoration: none;
    color: inherit;
  }

  .card-top {
    display: flex;
    align-items: flex-start;
    gap: var(--s-3);
  }

  .card-info {
    flex: 1;
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .card-name-row {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    min-width: 0;
  }

  .card-name {
    font: 600 var(--t-13) var(--font-sans);
    color: var(--ink-1);
    margin: 0;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .active-badge {
    flex-shrink: 0;
    font: 600 var(--t-9) var(--font-mono);
    color: var(--accent);
    background: var(--accent-soft, oklch(82% 0.14 145 / 0.12));
    border: 1px solid var(--accent);
    border-radius: var(--r-1);
    padding: 1px var(--s-2);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    line-height: 1.4;
  }

  .card-chips {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-1);
  }

  .card-ring { flex-shrink: 0; }

  .ring-placeholder {
    width: 64px;
    height: 64px;
    border-radius: 50%;
    background: var(--bg-2);
    border: 1px solid var(--line);
    animation: shimmer 1.5s ease-in-out infinite;
  }

  @keyframes shimmer {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.4; }
  }

  .card-actions {
    display: flex;
    gap: var(--s-2);
    border-top: 1px solid var(--line);
    padding: var(--s-2) var(--s-3);
  }

  .btn-small {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    background: transparent;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 2px var(--s-2);
    cursor: pointer;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    transition: background 0.1s, color 0.1s, border-color 0.1s;
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }

  .btn-small:hover {
    background: var(--bg-3);
    color: var(--ink-1);
    border-color: var(--line-strong);
  }

  .btn-small--danger:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
    background: var(--st-crit-soft);
  }

  .btn-small--add {
    color: var(--accent);
    border-color: var(--accent);
  }

  .btn-small--add:hover {
    background: var(--accent-soft, oklch(82% 0.14 145 / 0.12));
  }

  /* ── RIGHT: Grow Plan ── */
  .col-plan {
    min-width: 0;
  }

  .plan-sticky {
    position: sticky;
    top: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
  }

  .plan-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s-3) var(--s-3);
    border-bottom: 1px solid var(--line);
  }

  .plan-title {
    font: 600 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .plan-header-actions {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .plan-error {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--st-crit);
  }

  .btn-accent--sm {
    padding: 3px var(--s-3);
    font-size: var(--t-9);
  }

  /* ── Plan list ── */
  .plan-list {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: var(--s-2) var(--s-3);
    min-height: 80px;
  }

  .plan-empty {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 80px;
    border: 1px dashed var(--line-strong);
    border-radius: var(--r-1);
    color: var(--ink-4);
  }

  /* ── Transition insert button ── */
  .trans-insert {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
    height: 0;
    overflow: visible;
    position: relative;
    z-index: 1;
    border: none;
    background: transparent;
    cursor: pointer;
    opacity: 0;
    transition: opacity 0.15s;
    padding: 0;
    margin: -4px 0;
  }

  .plan-list:hover .trans-insert { opacity: 0.4; }
  .trans-insert:hover { opacity: 1 !important; }

  .trans-insert-label {
    font: 400 8px var(--font-mono);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .trans-insert svg { color: var(--ink-4); }
  .trans-insert:hover .trans-insert-label { color: var(--accent); }
  .trans-insert:hover svg { color: var(--accent); }

  /* ── Plan card ── */
  .plan-card {
    display: flex;
    flex-direction: column;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    background: var(--bg-2);
    margin-bottom: 2px;
    position: relative;
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .plan-card--recipe {
    border-left: 3px solid var(--card-accent);
  }

  .plan-card--transition {
    border-left: 3px solid transparent;
    background: repeating-linear-gradient(
      -45deg,
      var(--bg-2),
      var(--bg-2) 4px,
      var(--bg-inset) 4px,
      var(--bg-inset) 8px
    );
  }

  .plan-card--active {
    box-shadow: 0 0 0 1px var(--st-crit);
    border-color: var(--st-crit);
  }

  .plan-card--dragover {
    box-shadow: 0 -2px 0 0 var(--accent);
  }

  .plan-card:hover {
    border-color: var(--accent-line);
  }

  .plan-card-main {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-2);
    cursor: pointer;
    min-height: 30px;
  }

  .plan-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .plan-arrow {
    flex-shrink: 0;
    color: var(--ink-4);
    display: flex;
    align-items: center;
  }

  .plan-name {
    font: 500 var(--t-11) var(--font-mono);
    color: var(--ink-1);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    flex: 1;
    min-width: 0;
  }

  .plan-name--trans {
    color: var(--ink-3);
    font-weight: 400;
  }

  .plan-dur {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    flex-shrink: 0;
    white-space: nowrap;
  }

  .plan-open {
    font-style: italic;
  }

  .plan-card-btns {
    position: absolute;
    top: 2px;
    right: 2px;
    display: flex;
    gap: 1px;
    opacity: 0;
    transition: opacity 0.12s;
  }

  .plan-card:hover .plan-card-btns { opacity: 1; }

  .plan-btn-move,
  .plan-btn-del {
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: var(--r-1);
    background: transparent;
    color: var(--ink-4);
    cursor: pointer;
    transition: color 0.1s, background 0.1s;
  }

  .plan-btn-move:hover { background: var(--bg-3); color: var(--ink-1); }
  .plan-btn-move:disabled { opacity: 0.25; cursor: default; }

  .plan-btn-del:hover { background: var(--st-crit-soft); color: var(--st-crit); }

  /* ── Today marker on active card ── */
  .today-mark {
    position: absolute;
    left: -1px;
    top: 50%;
    transform: translate(-100%, -50%);
    display: flex;
    align-items: center;
    gap: 3px;
    padding-right: 4px;
  }

  .today-dot {
    width: 5px;
    height: 5px;
    border-radius: 50%;
    background: var(--st-crit);
    box-shadow: 0 0 6px var(--st-crit);
  }

  .today-text {
    font: 600 7px var(--font-mono);
    color: var(--st-crit);
    letter-spacing: 0.08em;
  }

  /* ── Duration editor ── */
  .dur-editor {
    padding: var(--s-2) var(--s-2);
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    background: var(--bg-inset);
  }

  .dur-toggle-row {
    display: flex;
    align-items: center;
  }

  .dur-toggle {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .dur-toggle input[type="checkbox"] {
    accent-color: var(--accent);
    width: 12px;
    height: 12px;
  }

  .dur-date {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font: 400 var(--t-10) var(--font-mono);
    padding: 3px var(--s-2);
    width: 100%;
  }

  .dur-date:focus { outline: none; border-color: var(--accent-line); }

  .dur-fields {
    display: flex;
    gap: var(--s-2);
  }

  .dur-field {
    display: flex;
    align-items: center;
    gap: 3px;
    flex: 1;
  }

  .dur-field input {
    width: 100%;
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font: 400 var(--t-10) var(--font-mono);
    padding: 3px var(--s-1);
    text-align: center;
  }

  .dur-field input:focus { outline: none; border-color: var(--accent-line); }

  .dur-field span {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    flex-shrink: 0;
  }

  .dur-actions {
    display: flex;
    gap: var(--s-2);
    justify-content: flex-end;
  }

  .dur-btn {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 2px var(--s-3);
    cursor: pointer;
    letter-spacing: 0.04em;
    text-transform: uppercase;
    transition: background 0.1s, color 0.1s;
  }

  .dur-btn:hover { background: var(--bg-3); color: var(--ink-1); }

  .dur-btn--apply {
    background: var(--accent);
    color: var(--bg-0);
    border-color: var(--accent);
  }

  .dur-btn--apply:hover { opacity: 0.85; }

  /* ── Today Preview ── */
  .today-preview {
    padding: var(--s-2) var(--s-3);
    border-top: 1px solid var(--line);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .tp-head {
    display: flex;
    align-items: baseline;
    gap: var(--s-2);
  }

  .tp-label {
    font: 600 8px var(--font-mono);
    color: var(--ink-4);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .tp-recipe {
    font: 600 var(--t-11) var(--font-mono);
    color: var(--accent);
  }

  .tp-date {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    margin-left: auto;
  }

  .tp-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-1) var(--s-3);
  }

  .tp-kv {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .tp-k {
    font: 500 7px var(--font-mono);
    color: var(--ink-4);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .tp-v {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
  }

  .tp-trans {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .tp-bar-track {
    flex: 1;
    height: 3px;
    background: var(--bg-3);
    border-radius: 2px;
    overflow: hidden;
  }

  .tp-bar-fill {
    height: 100%;
    background: var(--accent);
    border-radius: 2px;
    transition: width 0.3s ease;
  }

  .tp-pct {
    font: 600 var(--t-9) var(--font-mono);
    color: var(--accent);
    min-width: 28px;
    text-align: right;
  }

  /* ── Empty state ── */
  .empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 200px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
  }

  /* ── Shared ── */
  .section-label {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  .mono-label {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .btn-ghost {
    display: inline-flex;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-4);
    border: 1px solid var(--line-strong);
    border-radius: var(--r-2);
    background: transparent;
    color: var(--ink-2);
    font: 500 var(--t-11) var(--font-mono);
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: background 0.15s, border-color 0.15s, color 0.15s;
  }

  .btn-ghost:hover {
    background: var(--bg-2);
    border-color: var(--accent-line);
    color: var(--ink-1);
  }

  .btn-accent {
    display: inline-flex;
    align-items: center;
    padding: var(--s-2) var(--s-5);
    border: none;
    border-radius: var(--r-2);
    background: var(--accent);
    color: var(--bg-0);
    font: 600 var(--t-11) var(--font-mono);
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-accent:hover { opacity: 0.85; }
  .btn-accent:disabled { opacity: 0.4; cursor: not-allowed; }

  .btn-icon {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    background: transparent;
    color: var(--ink-3);
    cursor: pointer;
    transition: background 0.1s, color 0.1s;
  }

  .btn-icon:hover { background: var(--bg-2); color: var(--ink-1); }

  /* ── color-scheme for date inputs ── */
  .dur-date::-webkit-calendar-picker-indicator {
    filter: invert(0.7);
  }
</style>
