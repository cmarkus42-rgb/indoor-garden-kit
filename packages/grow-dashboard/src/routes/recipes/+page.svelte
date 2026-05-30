<script lang="ts">
  import { get, del, put } from '$lib/api.js';
  import type { RecipesResponse, RecipeSummary, RecipeData, DayPlanResponse } from '$lib/types.js';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import Chip from '$lib/components/Chip.svelte';
  import QueueTimeline from '$lib/components/QueueTimeline.svelte';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let recipes = $state<RecipeSummary[]>([]);
  let recipeDetails = $state<Record<string, RecipeData>>({});
  let activeRecipeName = $state<string | null>(null);
  let activating = $state<string | null>(null);
  let showImport = $state(false);
  let importJson = $state('');
  let importError = $state('');

  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  let nowMin = $state(getNowMin());

  async function load() {
    const [res, dayPlan] = await Promise.all([
      get<RecipesResponse>('/api/recipes'),
      get<DayPlanResponse>('/api/schedule/today').catch(() => null),
    ]);
    recipes = res.recipes;
    activeRecipeName = dayPlan?.recipe_name ?? null;
    // Batch-fetch full recipe data for PolarRing mini
    const details = await Promise.all(
      recipes.map(r =>
        get<RecipeData>(`/api/recipes/${encodeURIComponent(r.name)}`).catch(() => null)
      )
    );
    const map: Record<string, RecipeData> = {};
    for (const d of details) if (d) map[d.name] = d;
    recipeDetails = map;
  }

  async function handleActivate(name: string, e: Event) {
    e.stopPropagation();
    activating = name;
    try {
      await put('/api/queue', { entries: [{ recipe: name }] });
      activeRecipeName = name;
    } catch (err) {
      console.error('Failed to activate recipe:', err);
    } finally {
      activating = null;
    }
  }

  onMount(() => {
    load();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  async function handleDelete(name: string, e: Event) {
    e.stopPropagation();
    if (!confirm(`Delete recipe "${name}"?`)) return;
    await del(`/api/recipes/${encodeURIComponent(name)}`);
    await load();
  }

  async function handleClone(name: string, e: Event) {
    e.stopPropagation();
    const data = await get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`);
    const cloneName = `${data.name} (Copy)`;
    const cloned: RecipeData = { ...data, name: cloneName };
    await put(`/api/recipes/${encodeURIComponent(cloneName)}`, cloned);
    await load();
  }

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

  let fileInput: HTMLInputElement;

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
      await load();
    } catch (e) {
      importError = `Invalid JSON: ${e}`;
    }
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

  <!-- ── Queue Timeline ── -->
  <QueueTimeline />

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

  <!-- ── Recipe Grid ── -->
  {#if recipes.length === 0}
    <div class="empty-state">
      <span class="mono-label">NO RECIPES</span>
    </div>
  {:else}
    <div class="recipe-grid">
      {#each recipes as r}
        {@const detail = recipeDetails[r.name]}
        {@const isActive = activeRecipeName === r.name}
        <div class="recipe-card" class:recipe-card--active={isActive}>
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
            {#if isActive}
              <button class="btn-small btn-small--active" disabled>Active</button>
            {:else}
              <button
                class="btn-small btn-small--activate"
                onclick={(e) => handleActivate(r.name, e)}
                disabled={activating === r.name}
              >
                {activating === r.name ? 'Activating…' : 'Activate'}
              </button>
            {/if}
            <button class="btn-small" onclick={(e) => handleClone(r.name, e)}>Clone</button>
            <button class="btn-small btn-small--danger" onclick={(e) => handleDelete(r.name, e)}>Delete</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
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

  /* ── Recipe grid ── */
  .recipe-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s-3);
  }

  .recipe-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
    transition: border-color 0.15s, background 0.15s;
    display: flex;
    flex-direction: column;
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
    padding: var(--s-4);
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
    font: 600 var(--t-14) var(--font-sans);
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
    width: 80px;
    height: 80px;
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
    padding: var(--s-2) var(--s-4);
  }

  .btn-small {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    background: transparent;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 2px var(--s-2);
    cursor: pointer;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    transition: background 0.1s, color 0.1s, border-color 0.1s;
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

  .btn-small--activate {
    color: var(--accent);
    border-color: var(--accent);
  }

  .btn-small--activate:hover {
    background: var(--accent-soft, oklch(82% 0.14 145 / 0.12));
    color: var(--accent);
    border-color: var(--accent);
  }

  .btn-small--activate:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .btn-small--active {
    color: var(--accent);
    border-color: var(--accent);
    background: var(--accent-soft, oklch(82% 0.14 145 / 0.12));
    cursor: default;
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
</style>
