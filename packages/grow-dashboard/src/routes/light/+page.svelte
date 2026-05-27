<script lang="ts">
  import { get, put } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import TagesplanBanner from '$lib/components/TagesplanBanner.svelte';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import Chip from '$lib/components/Chip.svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import type {
    SchedulesResponse, LightSchedule,
    DayPlanResponse, QueueResponse, RecipesResponse, RecipeSummary, RecipeData
  } from '$lib/types.js';
  import { onMount } from 'svelte';

  let schedules = $state<LightSchedule[]>([]);
  let dayPlan = $state<DayPlanResponse | null>(null);
  let activeRecipe = $state<RecipeData | null>(null);
  let queue = $state<QueueResponse | null>(null);
  let allRecipes = $state<RecipeSummary[]>([]);
  let loading = $state(true);

  // Modal
  let showTransition = $state(false);
  let transitionTarget = $state('');
  let transitionDays = $state(7);
  let transitionStart = $state(new Date().toISOString().split('T')[0]);

  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  let nowMin = $state(getNowMin());

  async function load() {
    loading = true;
    const [schedRes, queueRes, recipesRes] = await Promise.all([
      get<SchedulesResponse>('/api/schedules'),
      get<QueueResponse>('/api/queue'),
      get<RecipesResponse>('/api/recipes'),
    ]);
    schedules = schedRes.schedules;
    queue = queueRes;
    allRecipes = recipesRes.recipes;

    try {
      dayPlan = await get<DayPlanResponse>('/api/schedule/today');
      if (dayPlan?.recipe_name) {
        activeRecipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(dayPlan.recipe_name)}`);
      }
    } catch {
      dayPlan = null;
    }
    loading = false;
  }

  onMount(() => {
    load();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'schedule_pushed') load();
  });

  function minuteToHHMM(m: number): string {
    const h = Math.floor((m % 1440) / 60);
    const min = (m % 1440) % 60;
    return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
  }

  async function handleTransition() {
    if (!transitionTarget || !dayPlan?.recipe_name) return;
    await put('/api/queue', {
      entries: [
        { recipe: dayPlan.recipe_name, until: transitionStart },
        { transition_to: transitionTarget, days: transitionDays },
        { recipe: transitionTarget },
      ],
    });
    showTransition = false;
    await load();
  }
</script>

<div class="page">
  <!-- ── Hero: Tagesplan Banner ── -->
  <div class="hero">
    {#if dayPlan && activeRecipe}
      <TagesplanBanner recipe={activeRecipe} dayPlan={dayPlan} nowMin={nowMin} />
    {:else if loading}
      <div class="banner-skeleton"></div>
    {:else}
      <div class="banner-empty">
        <span class="mono-label">NO ACTIVE SCHEDULE</span>
      </div>
    {/if}
  </div>

  <!-- ── 2-col: Active Recipe + Queue ── -->
  <div class="main-grid">
    <!-- Active Recipe -->
    <section class="panel">
      <div class="panel-header">
        <span class="section-label">ACTIVE RECIPE</span>
        {#if dayPlan}
          <StatusDot variant="ok" live />
        {:else}
          <StatusDot variant="warn" />
        {/if}
      </div>

      {#if dayPlan && activeRecipe}
        <div class="recipe-body">
          <div class="recipe-info">
            <h2 class="recipe-name">{dayPlan.recipe_name}</h2>
            <div class="recipe-period">
              <span class="mono-dim">{minuteToHHMM(dayPlan.main_on)}</span>
              <span class="period-arrow">→</span>
              <span class="mono-dim">{minuteToHHMM(dayPlan.main_off)}</span>
            </div>

            {#if dayPlan.transition_progress !== null}
              <div class="transition-progress">
                <div class="transition-label-row">
                  <span class="mono-label-sm">TRANSITION</span>
                  <span class="mono-dim-sm">{Math.round(dayPlan.transition_progress * 100)}%</span>
                </div>
                <div class="progress-bar">
                  <div class="progress-fill" style="width: {Math.round(dayPlan.transition_progress * 100)}%"></div>
                </div>
              </div>
            {/if}

            <button class="btn-ghost" onclick={() => showTransition = true}>
              Transition Recipe
            </button>
          </div>
          <div class="polar-wrap">
            <PolarRing recipe={activeRecipe} nowMin={nowMin} size="sm" />
          </div>
        </div>
      {:else if !loading}
        <p class="empty-msg">No active recipe</p>
      {/if}
    </section>

    <!-- Queue -->
    <section class="panel">
      <div class="panel-header">
        <span class="section-label">QUEUE</span>
        {#if queue?.entries.length}
          <Chip>{queue.entries.length}</Chip>
        {/if}
      </div>

      {#if queue && queue.entries.length > 0}
        <ol class="queue-list">
          {#each queue.entries as entry, i}
            <li class="queue-entry">
              <span class="queue-index">{i + 1}</span>
              <div class="queue-content">
                {#if entry.recipe}
                  <span class="queue-name">{entry.recipe}</span>
                  {#if entry.until}
                    <span class="queue-meta">until {entry.until}</span>
                  {/if}
                  <Chip variant="ok">recipe</Chip>
                {:else if entry.transition_to}
                  <span class="queue-name">{entry.transition_to}</span>
                  <span class="queue-meta">{entry.days} day transition</span>
                  <Chip variant="warn">transition</Chip>
                {/if}
              </div>
            </li>
          {/each}
        </ol>
      {:else}
        <p class="empty-msg">Queue empty</p>
      {/if}
    </section>
  </div>

  <!-- ── Schedule History ── -->
  <section class="panel">
    <div class="panel-header">
      <span class="section-label">SCHEDULE HISTORY</span>
      <Chip>{schedules.length}</Chip>
    </div>
    {#if schedules.length === 0}
      <p class="empty-msg">No schedules</p>
    {:else}
      <div class="table-wrap">
        <table class="data-table">
          <thead>
            <tr>
              <th>DEVICE</th>
              <th>DATE</th>
              <th>ON</th>
              <th>OFF</th>
              <th>PUSHED</th>
            </tr>
          </thead>
          <tbody>
            {#each schedules as s}
              <tr>
                <td class="td-mono">{s.device_id}</td>
                <td class="td-mono">{s.date}</td>
                <td class="td-mono">{s.on_time}</td>
                <td class="td-mono">{s.off_time}</td>
                <td class="td-mono td-dim">{s.pushed_at ?? '—'}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}
  </section>
</div>

<!-- ── Transition Modal ── -->
{#if showTransition}
  <!-- svelte-ignore a11y_click_events_have_key_events a11y_no_static_element_interactions -->
  <div class="modal-backdrop" role="presentation" onclick={() => showTransition = false}>
    <div class="modal" role="dialog" aria-modal="true" tabindex="-1" onclick={(e) => e.stopPropagation()}>
      <div class="modal-header">
        <span class="section-label">TRANSITION RECIPE</span>
        <button class="btn-icon" onclick={() => showTransition = false} aria-label="Close">
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <line x1="3" y1="3" x2="11" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
            <line x1="11" y1="3" x2="3" y2="11" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </button>
      </div>

      <div class="modal-body">
        <label class="field">
          <span class="field-label">TARGET RECIPE</span>
          <select class="input-select" bind:value={transitionTarget}>
            <option value="">— select —</option>
            {#each allRecipes as r}
              <option value={r.name}>{r.name}</option>
            {/each}
          </select>
        </label>

        <div class="field-row">
          <label class="field">
            <span class="field-label">TRANSITION DAYS</span>
            <input class="input-num" type="number" bind:value={transitionDays} min="1" max="30" />
          </label>
          <label class="field">
            <span class="field-label">START DATE</span>
            <input class="input-date" type="date" bind:value={transitionStart} />
          </label>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn-ghost" onclick={() => showTransition = false}>Cancel</button>
        <button class="btn-accent" onclick={handleTransition} disabled={!transitionTarget}>Apply</button>
      </div>
    </div>
  </div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
  }

  /* ── Hero ── */
  .hero { width: 100%; }

  .banner-skeleton {
    height: 120px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    animation: shimmer 1.5s ease-in-out infinite;
  }

  @keyframes shimmer {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.45; }
  }

  .banner-empty {
    height: 80px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    display: flex;
    align-items: center;
    justify-content: center;
  }

  /* ── Grid ── */
  .main-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-4);
  }

  /* ── Panels ── */
  .panel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4);
  }

  .panel-header {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    margin-bottom: var(--s-4);
    padding-bottom: var(--s-3);
    border-bottom: 1px solid var(--line);
  }

  /* ── Active Recipe ── */
  .recipe-body {
    display: flex;
    align-items: flex-start;
    gap: var(--s-4);
  }

  .recipe-info { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: var(--s-3); }

  .recipe-name {
    font: 600 var(--t-20) var(--font-sans);
    color: var(--ink-1);
    margin: 0;
    line-height: 1.2;
  }

  .recipe-period {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .period-arrow {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-4);
  }

  .transition-progress { display: flex; flex-direction: column; gap: var(--s-1); }

  .transition-label-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .progress-bar {
    height: 3px;
    background: var(--bg-3);
    border-radius: var(--r-pill);
    overflow: hidden;
  }

  .progress-fill {
    height: 100%;
    background: var(--st-recipe);
    border-radius: var(--r-pill);
    transition: width 0.4s ease;
  }

  .polar-wrap { flex-shrink: 0; }

  /* ── Queue ── */
  .queue-list {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .queue-entry {
    display: flex;
    align-items: flex-start;
    gap: var(--s-3);
    padding: var(--s-3);
    background: var(--bg-2);
    border-radius: var(--r-2);
    border: 1px solid var(--line);
  }

  .queue-index {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-4);
    min-width: 14px;
    padding-top: 3px;
  }

  .queue-content {
    flex: 1;
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .queue-name {
    font: 500 var(--t-13) var(--font-sans);
    color: var(--ink-1);
  }

  /* ── Table ── */
  .table-wrap { overflow-x: auto; }

  .data-table {
    width: 100%;
    border-collapse: collapse;
  }

  .data-table thead tr {
    border-bottom: 1px solid var(--line-strong);
  }

  .data-table th {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    text-align: left;
    padding: var(--s-2) var(--s-3);
    white-space: nowrap;
  }

  .data-table tbody tr {
    border-bottom: 1px solid var(--line);
    transition: background 0.1s;
  }

  .data-table tbody tr:hover { background: var(--bg-2); }
  .data-table tbody tr:last-child { border-bottom: none; }

  .td-mono {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-2);
    padding: var(--s-2) var(--s-3);
    letter-spacing: 0.02em;
  }

  .td-dim { color: var(--ink-4); }

  /* ── Typography ── */
  .section-label {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    flex: 1;
  }

  .mono-dim {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.04em;
  }

  .mono-label {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .mono-label-sm {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .mono-dim-sm {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    letter-spacing: 0.04em;
  }

  .queue-meta {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.04em;
  }

  .empty-msg {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-6) 0;
  }

  /* ── Buttons ── */
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
    align-self: flex-start;
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

  /* ── Modal ── */
  .modal-backdrop {
    position: fixed;
    inset: 0;
    background: oklch(0% 0 0 / 0.6);
    backdrop-filter: blur(4px);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 100;
  }

  .modal {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-6);
    width: 100%;
    max-width: 480px;
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    box-shadow: 0 16px 48px oklch(0% 0 0 / 0.5);
  }

  .modal-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .modal-body {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
  }

  .modal-footer {
    display: flex;
    justify-content: flex-end;
    gap: var(--s-2);
    padding-top: var(--s-3);
    border-top: 1px solid var(--line);
  }

  /* ── Fields ── */
  .field {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .field-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-3);
  }

  .field-label {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .input-select,
  .input-num,
  .input-date {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    color: var(--ink-1);
    font: 400 var(--t-12) var(--font-mono);
    padding: var(--s-2) var(--s-3);
    transition: border-color 0.15s;
    width: 100%;
    box-sizing: border-box;
  }

  .input-select:focus,
  .input-num:focus,
  .input-date:focus {
    outline: none;
    border-color: var(--accent-line);
  }
</style>
