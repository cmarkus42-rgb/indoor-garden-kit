<script lang="ts">
  import type { ChannelRule, ChannelRuleWindow } from '$lib/types.js';
  import ValueCard from './ValueCard.svelte';

  interface Props {
    name: string;
    rule: ChannelRule;
    originalRule: ChannelRule | undefined;
    onUpdate: (rule: ChannelRule) => void;
    onDelete: () => void;
    onRename: (name: string) => void;
  }

  let { name, rule, originalRule, onUpdate, onDelete, onRename }: Props = $props();

  /* ---------- dirty checks ---------- */

  function isDirtyOffset(): boolean {
    if (!originalRule) return true;
    return rule.offset_min !== originalRule.offset_min;
  }

  function isDirtyDuration(): boolean {
    if (!originalRule) return true;
    return rule.duration_min !== originalRule.duration_min;
  }

  function isDirtyRule(): boolean {
    if (!originalRule) return true;
    return rule.rule !== originalRule.rule;
  }

  /* ---------- validation ---------- */

  let errOffset = $derived(
    (rule.rule !== 'window' && rule.offset_min != null && rule.offset_min < 0) ? 'Offset >= 0' : ''
  );
  let errDuration = $derived(
    (rule.rule !== 'window' && rule.duration_min != null && rule.duration_min <= 0) ? 'Dauer > 0' : ''
  );

  /* ---------- updaters ---------- */

  function stepOffset(delta: number) {
    const v = Math.max(0, (rule.offset_min ?? 0) + delta);
    onUpdate({ ...rule, offset_min: v });
  }

  function stepDuration(delta: number) {
    const v = Math.max(1, (rule.duration_min ?? 1) + delta);
    onUpdate({ ...rule, duration_min: v });
  }

  function changeRule(newRule: ChannelRule['rule']) {
    if (newRule === 'window') {
      onUpdate({ rule: 'window', windows: [{ start: '12:00', duration_min: 30 }] });
    } else if (newRule === 'after_off') {
      onUpdate({ rule: 'after_off', offset_min: 5, duration_min: 15 });
    } else {
      onUpdate({ rule: 'before_on', offset_min: 15, duration_min: 30 });
    }
  }

  /* ---------- window helpers ---------- */

  function updateWindow(idx: number, patch: Partial<ChannelRuleWindow>) {
    if (!rule.windows) return;
    const windows = rule.windows.map((w, i) => (i === idx ? { ...w, ...patch } : w));
    onUpdate({ ...rule, windows });
  }

  function removeWindow(idx: number) {
    if (!rule.windows || rule.windows.length <= 1) return;
    onUpdate({ ...rule, windows: rule.windows.filter((_, i) => i !== idx) });
  }

  function addWindow() {
    const windows = [...(rule.windows ?? []), { start: '12:00', duration_min: 30 }];
    onUpdate({ ...rule, windows });
  }

  function stepWindowDuration(idx: number, delta: number) {
    if (!rule.windows) return;
    const dur = Math.max(1, rule.windows[idx].duration_min + delta);
    updateWindow(idx, { duration_min: dur });
  }

  /* ---------- name editing ---------- */

  let editingName = $state(false);
  let nameInput = $state('');

  function startEditing() {
    nameInput = name;
    editingName = true;
  }

  function commitName() {
    editingName = false;
    const trimmed = nameInput.trim();
    if (trimmed && trimmed !== name) {
      onRename(trimmed);
    }
  }
</script>

<div class="channel" class:channel--new={!originalRule}>
  <div class="channel-header">
    {#if editingName}
      <input
        class="name-input"
        type="text"
        bind:value={nameInput}
        onblur={commitName}
        onkeydown={(e) => { if (e.key === 'Enter') commitName(); }}
      />
    {:else}
      <button class="name-btn" onclick={startEditing}>
        {name}
      </button>
    {/if}

    <select
      class="rule-select"
      value={rule.rule}
      onchange={(e) => changeRule((e.target as HTMLSelectElement).value as ChannelRule['rule'])}
    >
      <option value="before_on">before_on</option>
      <option value="after_off">after_off</option>
      <option value="window">window</option>
    </select>
    {#if isDirtyRule()}
      <span class="tag tag--dirty">geaendert</span>
    {/if}

    <button class="delete-btn" onclick={onDelete} aria-label="Channel loeschen">
      <svg width="16" height="16" viewBox="0 0 16 16"><line x1="4" y1="4" x2="12" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="12" y1="4" x2="4" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
    </button>
  </div>

  {#if rule.rule === 'before_on' || rule.rule === 'after_off'}
    <div class="card-row">
      <ValueCard
        value={rule.offset_min ?? 0}
        unit="min"
        label="OFFSET"
        dirty={isDirtyOffset()}
        sub={isDirtyOffset() && originalRule?.offset_min != null ? `war ${originalRule.offset_min}` : undefined}
        error={errOffset || undefined}
        onStep={stepOffset}
      />
      <ValueCard
        value={rule.duration_min ?? 0}
        unit="min"
        label="DAUER"
        dirty={isDirtyDuration()}
        sub={isDirtyDuration() && originalRule?.duration_min != null ? `war ${originalRule.duration_min}` : undefined}
        error={errDuration || undefined}
        onStep={stepDuration}
      />
    </div>
  {/if}

  {#if rule.rule === 'window' && rule.windows}
    <div class="windows">
      {#each rule.windows as w, idx}
        <div class="window-row">
          <label class="window-time-label">
            <span class="field-label">START</span>
            <input
              class="time-input"
              type="time"
              value={w.start}
              onchange={(e) => updateWindow(idx, { start: (e.target as HTMLInputElement).value })}
            />
          </label>
          <ValueCard
            value={w.duration_min}
            unit="min"
            label="DAUER"
            dirty={false}
            onStep={(d) => stepWindowDuration(idx, d)}
          />
          {#if rule.windows && rule.windows.length > 1}
            <button class="remove-window" onclick={() => removeWindow(idx)} aria-label="Fenster entfernen">
              <svg width="14" height="14" viewBox="0 0 16 16"><line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
            </button>
          {/if}
        </div>
      {/each}
      <button class="add-window-link" onclick={addWindow}>+ Fenster hinzufuegen</button>
    </div>
  {/if}
</div>

<style>
  .channel {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .channel--new {
    border-color: var(--st-recipe);
    border-style: dashed;
  }

  .channel-header {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    flex-wrap: wrap;
  }

  .name-btn {
    background: none;
    border: none;
    font: 600 var(--t-14) var(--font-mono);
    color: var(--ink-1);
    cursor: pointer;
    padding: var(--s-1) 0;
  }

  .name-btn:hover {
    color: var(--accent);
  }

  .name-input {
    font: 600 var(--t-14) var(--font-mono);
    color: var(--ink-1);
    background: var(--bg-2);
    border: 1px solid var(--accent-line);
    border-radius: var(--r-2);
    padding: var(--s-1) var(--s-2);
    width: 140px;
  }

  .rule-select {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-2);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-1) var(--s-2);
    cursor: pointer;
  }

  .tag {
    font: 500 var(--t-9) var(--font-mono);
    padding: 2px var(--s-2);
    border-radius: var(--r-pill);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .tag--dirty {
    background: var(--st-recipe-soft);
    color: var(--st-recipe);
  }

  .delete-btn {
    margin-left: auto;
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    background: transparent;
    border: 1px solid transparent;
    border-radius: var(--r-2);
    color: var(--ink-4);
    cursor: pointer;
    transition: color 0.1s, border-color 0.1s, background 0.1s;
  }

  .delete-btn:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
    background: var(--st-crit-soft);
  }

  .card-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-3);
  }

  .windows {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .window-row {
    display: flex;
    align-items: flex-end;
    gap: var(--s-3);
  }

  .window-time-label {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .field-label {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .time-input {
    font: 400 var(--t-14) var(--font-mono);
    color: var(--ink-1);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-2) var(--s-3);
  }

  .time-input:focus {
    border-color: var(--accent-line);
    outline: none;
    box-shadow: 0 0 0 1px var(--accent-line);
  }

  .remove-window {
    display: grid;
    place-items: center;
    width: 28px;
    height: 28px;
    flex-shrink: 0;
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    color: var(--ink-4);
    cursor: pointer;
    margin-bottom: var(--s-1);
  }

  .remove-window:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
  }

  .add-window-link {
    background: none;
    border: none;
    font: 500 var(--t-10) var(--font-mono);
    color: var(--accent);
    cursor: pointer;
    padding: var(--s-1) 0;
    text-align: left;
    letter-spacing: 0.04em;
  }

  .add-window-link:hover {
    text-decoration: underline;
  }
</style>
