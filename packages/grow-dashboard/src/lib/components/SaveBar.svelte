<script lang="ts">
  import type { RecipeData } from '$lib/types.js';

  interface DiffEntry {
    field: string;
    before: string;
    after: string;
  }

  interface Props {
    current: RecipeData;
    original: RecipeData;
    hasErrors: boolean;
    saving: boolean;
    onSave: () => void;
    onCancel: () => void;
  }

  let { current, original, hasErrors, saving, onSave, onCancel }: Props = $props();

  let expanded = $state(false);

  /* ---------- diff computation ---------- */

  function buildDiffs(): DiffEntry[] {
    const diffs: DiffEntry[] = [];

    if (current.photoperiod.on !== original.photoperiod.on) {
      diffs.push({ field: 'On', before: original.photoperiod.on, after: current.photoperiod.on });
    }
    if (current.photoperiod.off !== original.photoperiod.off) {
      diffs.push({ field: 'Off', before: original.photoperiod.off, after: current.photoperiod.off });
    }

    const dimKeys = ['sunrise_min', 'sunset_min', 'max_pct', 'min_pct'] as const;
    const dimLabels: Record<string, string> = {
      sunrise_min: 'Sunrise', sunset_min: 'Sunset', max_pct: 'Max %', min_pct: 'Min %',
    };
    for (const k of dimKeys) {
      if (current.dimming[k] !== original.dimming[k]) {
        diffs.push({ field: dimLabels[k], before: String(original.dimming[k]), after: String(current.dimming[k]) });
      }
    }

    const allChNames = new Set([...Object.keys(current.channels), ...Object.keys(original.channels)]);
    for (const ch of allChNames) {
      const cur = current.channels[ch];
      const orig = original.channels[ch];
      if (!orig && cur) {
        diffs.push({ field: `Ch: ${ch}`, before: '—', after: `new (${cur.rule})` });
      } else if (orig && !cur) {
        diffs.push({ field: `Ch: ${ch}`, before: orig.rule, after: 'deleted' });
      } else if (orig && cur) {
        if (JSON.stringify(cur) !== JSON.stringify(orig)) {
          diffs.push({ field: `Ch: ${ch}`, before: JSON.stringify(orig), after: JSON.stringify(cur) });
        }
      }
    }

    return diffs;
  }

  let diffs = $derived(buildDiffs());
  let changeCount = $derived(diffs.length);
  let hasChanges = $derived(changeCount > 0);
</script>

{#if hasChanges}
  <div class="save-bar" class:save-bar--error={hasErrors}>
    <div class="bar-main">
      <button class="expand-btn" onclick={() => expanded = !expanded} aria-label="Show diff">
        <svg
          width="16" height="16" viewBox="0 0 16 16"
          style="transform: rotate({expanded ? '180deg' : '0deg'}); transition: transform 0.15s"
        >
          <polyline points="4,6 8,10 12,6" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="change-count">{changeCount} {changeCount === 1 ? 'change' : 'changes'}</span>
      </button>

      <div class="bar-actions">
        <button class="cancel-btn" onclick={onCancel} disabled={saving}>Cancel</button>
        <button
          class="save-btn"
          onclick={onSave}
          disabled={hasErrors || saving}
        >
          {#if saving}
            Saving…
          {:else if hasErrors}
            Save — fix errors first
          {:else}
            Save
          {/if}
        </button>
      </div>
    </div>

    {#if expanded}
      <div class="diff-grid">
        <div class="diff-head">Field</div>
        <div class="diff-head">Before</div>
        <div class="diff-head">After</div>
        {#each diffs as d}
          <div class="diff-field">{d.field}</div>
          <div class="diff-before">{d.before}</div>
          <div class="diff-after">{d.after}</div>
        {/each}
      </div>
    {/if}
  </div>
{/if}

<style>
  .save-bar {
    position: sticky;
    bottom: 0;
    background: var(--bg-1);
    border-top: 1px solid var(--line);
    border-radius: var(--r-3) var(--r-3) 0 0;
    padding: var(--s-3) var(--s-4);
    box-shadow: 0 -4px 24px oklch(0% 0 0 / 0.3);
    z-index: 50;
  }

  .bar-main {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-3);
    flex-wrap: wrap;
  }

  .expand-btn {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    background: none;
    border: none;
    color: var(--ink-2);
    font: 500 var(--t-11) var(--font-mono);
    cursor: pointer;
    padding: var(--s-1) 0;
  }

  .expand-btn:hover {
    color: var(--ink-1);
  }

  .change-count {
    font-variant-numeric: tabular-nums;
  }

  .bar-actions {
    display: flex;
    gap: var(--s-2);
    align-items: center;
  }

  .cancel-btn {
    font: 500 var(--t-11) var(--font-mono);
    color: var(--ink-3);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-2) var(--s-4);
    cursor: pointer;
    transition: border-color 0.1s, color 0.1s;
  }

  .cancel-btn:hover {
    border-color: var(--ink-4);
    color: var(--ink-1);
  }

  .cancel-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .save-btn {
    font: 600 var(--t-11) var(--font-mono);
    color: var(--bg-0);
    background: var(--accent);
    border: none;
    border-radius: var(--r-2);
    padding: var(--s-2) var(--s-5);
    cursor: pointer;
    transition: opacity 0.1s, filter 0.1s;
  }

  .save-btn:hover:not(:disabled) {
    filter: brightness(1.1);
  }

  .save-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .save-bar--error .save-btn {
    background: var(--ink-4);
  }

  .diff-grid {
    display: grid;
    grid-template-columns: minmax(80px, 1fr) minmax(80px, 1fr) minmax(80px, 1fr);
    gap: 1px;
    margin-top: var(--s-3);
    border-top: 1px solid var(--line);
    padding-top: var(--s-3);
    max-height: 240px;
    overflow-y: auto;
  }

  .diff-head {
    font: 600 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding-bottom: var(--s-2);
  }

  .diff-field {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-2);
    padding: var(--s-1) 0;
    word-break: break-all;
  }

  .diff-before {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-4);
    padding: var(--s-1) 0;
    word-break: break-all;
  }

  .diff-after {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--st-recipe);
    padding: var(--s-1) 0;
    word-break: break-all;
  }
</style>
