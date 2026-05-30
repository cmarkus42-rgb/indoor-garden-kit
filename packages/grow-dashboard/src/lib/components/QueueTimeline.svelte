<script lang="ts">
  import { get, put } from '$lib/api.js';
  import type { QueueEntry, QueueResponse, RecipeSummary, RecipesResponse, DayPlanResponse } from '$lib/types.js';
  import { onMount } from 'svelte';

  // ── State ──
  let queue = $state<QueueEntry[]>([]);
  let recipes = $state<RecipeSummary[]>([]);
  let today = $state<DayPlanResponse | null>(null);
  let saving = $state(false);
  let dirty = $state(false);
  let error = $state('');
  let expanded = $state(true);

  // ── Editor draft ──
  let draftRecipe = $state('');
  let draftUntil = $state('');
  let draftTransDays = $state(7);

  // ── Palette for recipe segments ──
  const PALETTE = [
    'oklch(72% 0.18 145)',  // green
    'oklch(68% 0.20 280)',  // indigo
    'oklch(75% 0.18 55)',   // amber
    'oklch(70% 0.22 330)',  // magenta
    'oklch(78% 0.14 200)',  // teal
    'oklch(72% 0.20 25)',   // coral
  ];

  function recipeColor(name: string): string {
    let h = 0;
    for (let i = 0; i < name.length; i++) h = ((h << 5) - h + name.charCodeAt(i)) | 0;
    return PALETTE[Math.abs(h) % PALETTE.length];
  }

  // ── Computed timeline data ──
  let segments = $derived(computeSegments(queue));

  interface Segment {
    type: 'recipe' | 'transition';
    label: string;
    sublabel: string;
    color: string;
    width: number; // percentage
    openEnd: boolean;
  }

  function computeSegments(entries: QueueEntry[]): Segment[] {
    if (!entries.length) return [];
    const now = new Date();
    const segs: Segment[] = [];

    // Calculate total days for proportional widths
    let totalDays = 0;
    let hasOpenEnd = false;
    const durations: number[] = [];

    for (const e of entries) {
      if (e.recipe && e.until) {
        const end = new Date(e.until);
        const days = Math.max(1, Math.ceil((end.getTime() - now.getTime()) / 86400000));
        durations.push(days);
        totalDays += days;
      } else if (e.transition_to && e.days) {
        durations.push(e.days);
        totalDays += e.days;
      } else {
        // Open-ended last entry
        durations.push(0);
        hasOpenEnd = true;
      }
    }

    // Reserve 15% for open end
    const openEndPct = hasOpenEnd ? 15 : 0;
    const distributable = 100 - openEndPct;

    for (let i = 0; i < entries.length; i++) {
      const e = entries[i];
      const isOpenEnd = !e.until && e.recipe && !e.transition_to;

      if (e.recipe) {
        segs.push({
          type: 'recipe',
          label: e.recipe,
          sublabel: e.until ? `until ${e.until}` : '',
          color: recipeColor(e.recipe),
          width: isOpenEnd ? openEndPct : (totalDays > 0 ? (durations[i] / totalDays) * distributable : distributable / entries.length),
          openEnd: !!isOpenEnd,
        });
      } else if (e.transition_to) {
        segs.push({
          type: 'transition',
          label: `→ ${e.transition_to}`,
          sublabel: `${e.days}d`,
          color: recipeColor(e.transition_to),
          width: totalDays > 0 ? (durations[i] / totalDays) * distributable : 8,
          openEnd: false,
        });
      }
    }
    return segs;
  }

  // ── Today marker position (percentage along the timeline) ──
  let todayPct = $derived(computeTodayPct(queue));

  function computeTodayPct(entries: QueueEntry[]): number {
    if (!entries.length) return 0;
    const now = Date.now();
    let totalMs = 0;
    let elapsedMs = 0;

    // Find earliest start — approximate as "now minus elapsed in first entry"
    // For simplicity, compute based on segment durations
    for (const e of entries) {
      if (e.recipe && e.until) {
        const end = new Date(e.until).getTime();
        const dur = Math.max(0, end - now);
        totalMs += dur;
      } else if (e.transition_to && e.days) {
        totalMs += e.days * 86400000;
      }
    }

    // Today is at the boundary of the first segment's remaining time
    if (totalMs <= 0) return 0;

    // Place marker at proportion of first entry's elapsed time
    const first = entries[0];
    if (first.recipe && first.until) {
      const end = new Date(first.until).getTime();
      const remaining = Math.max(0, end - now);
      const segTotal = remaining; // from now to end
      // Marker is at position 0 of the remaining timeline (start)
      return 2; // Small offset so it's visible at the start
    }
    return 2;
  }

  // ── API ──
  async function loadQueue() {
    try {
      const res = await get<QueueResponse>('/api/queue');
      queue = res.entries;
      dirty = false;
    } catch {
      queue = [];
    }
  }

  async function loadRecipes() {
    try {
      const res = await get<RecipesResponse>('/api/recipes');
      recipes = res.recipes;
      if (recipes.length && !draftRecipe) draftRecipe = recipes[0].name;
    } catch {
      recipes = [];
    }
  }

  async function loadToday() {
    try {
      today = await get<DayPlanResponse>('/api/schedule/today');
    } catch {
      today = null;
    }
  }

  async function saveQueue() {
    saving = true;
    error = '';
    try {
      await put('/api/queue', { entries: queue });
      dirty = false;
      await loadToday();
    } catch (e) {
      error = `Save failed: ${e}`;
    } finally {
      saving = false;
    }
  }

  function addPhase() {
    if (!draftRecipe) return;
    queue = [...queue, { recipe: draftRecipe, until: draftUntil || undefined }];
    draftUntil = '';
    dirty = true;
  }

  function addTransition() {
    if (!draftRecipe || draftTransDays < 1) return;
    queue = [...queue, { transition_to: draftRecipe, days: draftTransDays }];
    dirty = true;
  }

  function removeEntry(idx: number) {
    queue = queue.filter((_, i) => i !== idx);
    dirty = true;
  }

  function fmtMinutes(min: number): string {
    const h = Math.floor(min / 60);
    const m = min % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  onMount(() => {
    loadQueue();
    loadRecipes();
    loadToday();
  });
</script>

<section class="qt">
  <!-- ── Section Header ── -->
  <button class="qt-header" onclick={() => expanded = !expanded}>
    <span class="qt-label">GROW QUEUE</span>
    <span class="qt-toggle">{expanded ? '▾' : '▸'}</span>
  </button>

  {#if expanded}
    <!-- ── Timeline Bar ── -->
    <div class="tl-wrap">
      {#if segments.length === 0}
        <div class="tl-empty">No queue configured</div>
      {:else}
        <div class="tl-bar">
          <!-- Today marker -->
          <div class="tl-today" style="left: {todayPct}%">
            <div class="tl-today-dot"></div>
            <div class="tl-today-line"></div>
            <span class="tl-today-label">TODAY</span>
          </div>

          {#each segments as seg, i}
            <div
              class="tl-seg"
              class:tl-seg--trans={seg.type === 'transition'}
              class:tl-seg--open={seg.openEnd}
              style="width: {seg.width}%; --seg-color: {seg.color};"
            >
              <div class="tl-seg-inner">
                <span class="tl-seg-name">{seg.label}</span>
                {#if seg.sublabel}
                  <span class="tl-seg-sub">{seg.sublabel}</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>

    <div class="qt-body">
      <!-- ── Today Preview ── -->
      {#if today}
        <div class="tp">
          <div class="tp-head">
            <span class="tp-recipe">{today.recipe_name}</span>
            <span class="tp-date">{today.date}</span>
          </div>

          <div class="tp-grid">
            <div class="tp-kv">
              <span class="tp-k">PHOTOPERIOD</span>
              <span class="tp-v">{fmtMinutes(today.main_on)} — {fmtMinutes(today.main_off)}</span>
            </div>
            <div class="tp-kv">
              <span class="tp-k">DIMMING</span>
              <span class="tp-v">
                {today.dimming_curve.length ? `${today.dimming_curve[0].pct}% — ${Math.max(...today.dimming_curve.map(d => d.pct))}%` : '—'}
              </span>
            </div>
            {#if (today as any).climate}
              <div class="tp-kv">
                <span class="tp-k">FAN</span>
                <span class="tp-v">{(today as any).climate.fan_intensity ?? '—'}%</span>
              </div>
              <div class="tp-kv">
                <span class="tp-k">VPD TARGET</span>
                <span class="tp-v">{(today as any).climate.vpd_target ?? '—'} kPa</span>
              </div>
            {/if}
            {#if (today as any).irrigation}
              <div class="tp-kv">
                <span class="tp-k">DRY</span>
                <span class="tp-v">{(today as any).irrigation.dry_threshold ?? '—'}</span>
              </div>
              <div class="tp-kv">
                <span class="tp-k">WET</span>
                <span class="tp-v">{(today as any).irrigation.wet_threshold ?? '—'}</span>
              </div>
            {/if}
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

      <!-- ── Queue Editor ── -->
      <div class="qe">
        <div class="qe-head">
          <span class="qe-label">ENTRIES</span>
          {#if error}
            <span class="qe-error">{error}</span>
          {/if}
        </div>

        <!-- Entry list -->
        {#if queue.length > 0}
          <div class="qe-list">
            {#each queue as entry, idx}
              <div class="qe-item">
                {#if entry.recipe}
                  <span class="qe-dot" style="background: {recipeColor(entry.recipe)}"></span>
                  <span class="qe-name">{entry.recipe}</span>
                  {#if entry.until}
                    <span class="qe-meta">until {entry.until}</span>
                  {:else}
                    <span class="qe-meta qe-meta--open">open end</span>
                  {/if}
                {:else if entry.transition_to}
                  <span class="qe-arrow">→</span>
                  <span class="qe-name">{entry.transition_to}</span>
                  <span class="qe-meta">{entry.days}d transition</span>
                {/if}
                <button class="qe-del" onclick={() => removeEntry(idx)} aria-label="Remove entry">
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none">
                    <line x1="1" y1="1" x2="9" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                    <line x1="9" y1="1" x2="1" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                  </svg>
                </button>
              </div>
            {/each}
          </div>
        {/if}

        <!-- Add controls -->
        <div class="qe-add">
          <select class="qe-select" bind:value={draftRecipe}>
            {#each recipes as r}
              <option value={r.name}>{r.name}</option>
            {/each}
          </select>

          <div class="qe-row">
            <input type="date" class="qe-input" bind:value={draftUntil} />
            <button class="qe-btn" onclick={addPhase}>+ Phase</button>
          </div>
          <div class="qe-row">
            <input type="number" class="qe-input qe-input--narrow" bind:value={draftTransDays} min="1" max="60" />
            <span class="qe-unit">days</span>
            <button class="qe-btn" onclick={addTransition}>+ Transition</button>
          </div>
        </div>

        {#if dirty}
          <div class="qe-save">
            <button class="qe-save-btn" onclick={saveQueue} disabled={saving}>
              {saving ? 'Saving…' : 'Save Queue'}
            </button>
          </div>
        {/if}
      </div>
    </div>
  {/if}
</section>

<style>
  /* ── Container ── */
  .qt {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
  }

  .qt-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    padding: var(--s-3) var(--s-4);
    background: transparent;
    border: none;
    cursor: pointer;
    color: var(--ink-3);
  }

  .qt-header:hover { background: var(--bg-2); }

  .qt-label {
    font: 500 var(--t-9) var(--font-mono);
    letter-spacing: 0.14em;
    text-transform: uppercase;
    color: var(--ink-3);
  }

  .qt-toggle {
    font-size: var(--t-11);
    color: var(--ink-4);
  }

  /* ── Timeline Bar ── */
  .tl-wrap {
    padding: 0 var(--s-4) var(--s-3);
  }

  .tl-empty {
    font: 400 var(--t-11) var(--font-mono);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-3) 0;
  }

  .tl-bar {
    display: flex;
    height: 36px;
    border-radius: var(--r-1);
    overflow: visible;
    position: relative;
    gap: 1px;
  }

  .tl-seg {
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: var(--seg-color);
    opacity: 0.85;
    min-width: 24px;
    overflow: hidden;
    position: relative;
    transition: opacity 0.15s;
  }

  .tl-seg:first-child { border-radius: var(--r-1) 0 0 var(--r-1); }
  .tl-seg:last-child { border-radius: 0 var(--r-1) var(--r-1) 0; }
  .tl-seg:only-child { border-radius: var(--r-1); }

  .tl-seg:hover { opacity: 1; }

  .tl-seg--trans {
    background: repeating-linear-gradient(
      -45deg,
      var(--seg-color),
      var(--seg-color) 3px,
      transparent 3px,
      transparent 7px
    );
    opacity: 0.6;
  }

  .tl-seg--open {
    border: 1px dashed var(--seg-color);
    background: transparent;
    opacity: 0.5;
  }

  .tl-seg-inner {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 1px;
    padding: 0 var(--s-1);
    min-width: 0;
  }

  .tl-seg-name {
    font: 600 var(--t-9) var(--font-mono);
    color: var(--bg-0);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 100%;
    line-height: 1.2;
  }

  .tl-seg--trans .tl-seg-name,
  .tl-seg--open .tl-seg-name {
    color: var(--ink-2);
  }

  .tl-seg-sub {
    font: 400 8px var(--font-mono);
    color: var(--bg-0);
    opacity: 0.7;
    white-space: nowrap;
    line-height: 1;
  }

  .tl-seg--trans .tl-seg-sub,
  .tl-seg--open .tl-seg-sub {
    color: var(--ink-3);
  }

  /* ── Today Marker ── */
  .tl-today {
    position: absolute;
    top: -6px;
    bottom: -14px;
    z-index: 2;
    pointer-events: none;
    transform: translateX(-50%);
  }

  .tl-today-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--st-crit);
    box-shadow: 0 0 6px var(--st-crit);
    margin: 0 auto;
  }

  .tl-today-line {
    width: 1.5px;
    height: 100%;
    background: var(--st-crit);
    margin: 0 auto;
    opacity: 0.7;
  }

  .tl-today-label {
    display: block;
    font: 600 7px var(--font-mono);
    color: var(--st-crit);
    letter-spacing: 0.1em;
    text-align: center;
    margin-top: 1px;
  }

  /* ── Body (Today Preview + Editor) ── */
  .qt-body {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 1px;
    background: var(--line);
    border-top: 1px solid var(--line);
  }

  /* ── Today Preview ── */
  .tp {
    background: var(--bg-1);
    padding: var(--s-3) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .tp-head {
    display: flex;
    align-items: baseline;
    gap: var(--s-2);
  }

  .tp-recipe {
    font: 600 var(--t-12) var(--font-mono);
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
    gap: var(--s-1) var(--s-4);
  }

  .tp-kv {
    display: flex;
    flex-direction: column;
    gap: 1px;
  }

  .tp-k {
    font: 500 8px var(--font-mono);
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
    margin-top: var(--s-1);
  }

  .tp-bar-track {
    flex: 1;
    height: 4px;
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
    min-width: 32px;
    text-align: right;
  }

  /* ── Queue Editor ── */
  .qe {
    background: var(--bg-1);
    padding: var(--s-3) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .qe-head {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .qe-label {
    font: 500 8px var(--font-mono);
    color: var(--ink-4);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .qe-error {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--st-crit);
    margin-left: auto;
  }

  .qe-list {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .qe-item {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding: 3px var(--s-2);
    border-radius: var(--r-1);
    background: var(--bg-2);
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-2);
  }

  .qe-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .qe-arrow {
    color: var(--ink-4);
    font-size: var(--t-10);
    flex-shrink: 0;
    width: 6px;
    text-align: center;
  }

  .qe-name {
    color: var(--ink-1);
    font-weight: 500;
  }

  .qe-meta {
    color: var(--ink-4);
    margin-left: auto;
    font-size: 10px;
  }

  .qe-meta--open {
    color: var(--ink-4);
    font-style: italic;
  }

  .qe-del {
    display: grid;
    place-items: center;
    width: 18px;
    height: 18px;
    border: none;
    border-radius: var(--r-1);
    background: transparent;
    color: var(--ink-4);
    cursor: pointer;
    flex-shrink: 0;
    transition: color 0.1s, background 0.1s;
  }

  .qe-del:hover {
    background: var(--st-crit-soft);
    color: var(--st-crit);
  }

  /* ── Add controls ── */
  .qe-add {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
    margin-top: var(--s-1);
  }

  .qe-select,
  .qe-input {
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font: 400 var(--t-10) var(--font-mono);
    padding: 3px var(--s-2);
    outline: none;
  }

  .qe-select { width: 100%; }

  .qe-select:focus,
  .qe-input:focus {
    border-color: var(--accent-line);
  }

  .qe-row {
    display: flex;
    align-items: center;
    gap: var(--s-1);
  }

  .qe-input { flex: 1; min-width: 0; }
  .qe-input--narrow { flex: 0 0 56px; text-align: center; }

  .qe-unit {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
  }

  .qe-btn {
    flex-shrink: 0;
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-2);
    background: var(--bg-2);
    border: 1px solid var(--line-strong);
    border-radius: var(--r-1);
    padding: 3px var(--s-3);
    cursor: pointer;
    letter-spacing: 0.04em;
    white-space: nowrap;
    transition: background 0.1s, color 0.1s, border-color 0.1s;
  }

  .qe-btn:hover {
    background: var(--bg-3);
    color: var(--ink-1);
    border-color: var(--accent-line);
  }

  /* ── Save ── */
  .qe-save {
    display: flex;
    justify-content: flex-end;
    margin-top: var(--s-1);
  }

  .qe-save-btn {
    font: 600 var(--t-10) var(--font-mono);
    color: var(--bg-0);
    background: var(--accent);
    border: none;
    border-radius: var(--r-1);
    padding: var(--s-1) var(--s-4);
    cursor: pointer;
    letter-spacing: 0.06em;
    text-transform: uppercase;
    transition: opacity 0.15s;
  }

  .qe-save-btn:hover { opacity: 0.85; }
  .qe-save-btn:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── color-scheme for date inputs ── */
  .qe-input[type="date"]::-webkit-calendar-picker-indicator {
    filter: invert(0.7);
  }
</style>
