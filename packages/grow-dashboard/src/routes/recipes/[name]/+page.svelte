<script lang="ts">
  import { get, put } from '$lib/api.js';
  import type { RecipeData, ChannelRule } from '$lib/types.js';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  let recipe = $state<RecipeData | null>(null);
  let jsonText = $state('');
  let activeTab = $state<'visual' | 'json'>('visual');
  let saving = $state(false);
  let error = $state('');

  const name = $derived(decodeURIComponent($page.params.name ?? ''));

  async function load() {
    try {
      recipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`);
      jsonText = JSON.stringify(recipe, null, 2);
    } catch {
      error = 'Recipe not found';
    }
  }

  onMount(() => { load(); });

  async function save() {
    if (!recipe) return;
    saving = true;
    error = '';
    try {
      if (activeTab === 'json') {
        recipe = JSON.parse(jsonText);
      }
      await put(`/api/recipes/${encodeURIComponent(name)}`, recipe);
      jsonText = JSON.stringify(recipe, null, 2);
    } catch (e) {
      error = `Save failed: ${e}`;
    }
    saving = false;
  }

  function addChannel() {
    if (!recipe) return;
    const ch = prompt('Channel name:');
    if (!ch) return;
    recipe.channels[ch] = { rule: 'before_on', offset_min: 15 };
    recipe = { ...recipe };
  }

  function removeChannel(ch: string) {
    if (!recipe) return;
    delete recipe.channels[ch];
    recipe = { ...recipe };
  }

  function updateRule(ch: string, rule: 'before_on' | 'after_off' | 'window') {
    if (!recipe) return;
    if (rule === 'window') {
      recipe.channels[ch] = { rule, windows: [{ start: '12:00', duration_min: 30 }] };
    } else if (rule === 'after_off') {
      recipe.channels[ch] = { rule, offset_min: 5, duration_min: 15 };
    } else {
      recipe.channels[ch] = { rule, offset_min: 15 };
    }
    recipe = { ...recipe };
  }

  // 24h preview bar helpers
  function minuteToPercent(m: number): number {
    return (m / 1440) * 100;
  }

  function parseHHMM(s: string): number {
    const [h, m] = s.split(':').map(Number);
    return h * 60 + m;
  }

  let previewMainOn = $derived(recipe ? parseHHMM(recipe.photoperiod.on) : 0);
  let previewMainOff = $derived(recipe ? parseHHMM(recipe.photoperiod.off) : 0);
  let previewMainWidth = $derived(
    previewMainOff > previewMainOn
      ? previewMainOff - previewMainOn
      : 1440 - previewMainOn + previewMainOff
  );
</script>

<h1>Edit: {name}</h1>

{#if error}
  <p class="error">{error}</p>
{/if}

{#if recipe}
  <div class="tabs">
    <button class:active={activeTab === 'visual'} onclick={() => activeTab = 'visual'}>Visual</button>
    <button class:active={activeTab === 'json'} onclick={() => { activeTab = 'json'; jsonText = JSON.stringify(recipe, null, 2); }}>JSON</button>
  </div>

  {#if activeTab === 'visual'}
    <section>
      <h2>Photoperiod</h2>
      <label>On: <input type="time" bind:value={recipe.photoperiod.on} /></label>
      <label>Off: <input type="time" bind:value={recipe.photoperiod.off} /></label>
    </section>

    <section>
      <h2>Dimming</h2>
      <label>Sunrise (min): <input type="range" min="0" max="120" bind:value={recipe.dimming.sunrise_min} /> {recipe.dimming.sunrise_min}</label>
      <label>Sunset (min): <input type="range" min="0" max="120" bind:value={recipe.dimming.sunset_min} /> {recipe.dimming.sunset_min}</label>
      <label>Max %: <input type="range" min="0" max="100" bind:value={recipe.dimming.max_pct} /> {recipe.dimming.max_pct}</label>
      <label>Min %: <input type="range" min="0" max="100" bind:value={recipe.dimming.min_pct} /> {recipe.dimming.min_pct}</label>
    </section>

    <section>
      <h2>Channels</h2>
      {#each Object.entries(recipe.channels) as [ch, rule]}
        <div class="channel-card">
          <strong>{ch}</strong>
          <button class="small" onclick={() => removeChannel(ch)}>Remove</button>
          <select value={rule.rule} onchange={(e) => updateRule(ch, (e.target as HTMLSelectElement).value as ChannelRule['rule'])}>
            <option value="before_on">before_on</option>
            <option value="after_off">after_off</option>
            <option value="window">window</option>
          </select>
          {#if rule.rule === 'before_on' || rule.rule === 'after_off'}
            <label>Offset (min): <input type="number" bind:value={rule.offset_min} min="0" /></label>
            <label>Duration (min): <input type="number" bind:value={rule.duration_min} min="0" /></label>
          {/if}
          {#if rule.rule === 'window' && rule.windows}
            {#each rule.windows as w}
              <div class="window-entry">
                <label>Start: <input type="time" bind:value={w.start} /></label>
                <label>Duration: <input type="number" bind:value={w.duration_min} min="1" /></label>
              </div>
            {/each}
          {/if}
        </div>
      {/each}
      <button onclick={addChannel}>Add Channel</button>
    </section>

    <section>
      <h2>24h Preview</h2>
      <div class="timeline">
        <div class="timeline-bar main" style="left: {minuteToPercent(previewMainOn)}%; width: {minuteToPercent(previewMainWidth)}%"></div>
        {#each Object.entries(recipe.channels) as [ch, rule]}
          {#if rule.rule === 'before_on'}
            <div class="timeline-bar channel" title={ch} style="left: {minuteToPercent(previewMainOn - (rule.offset_min ?? 0))}%; width: {minuteToPercent(rule.duration_min ?? rule.offset_min ?? 0)}%"></div>
          {/if}
          {#if rule.rule === 'after_off'}
            {@const offMin = previewMainOff > previewMainOn ? previewMainOff : previewMainOff + 1440}
            <div class="timeline-bar channel" title={ch} style="left: {minuteToPercent(offMin + (rule.offset_min ?? 0))}%; width: {minuteToPercent(rule.duration_min ?? 0)}%"></div>
          {/if}
          {#if rule.rule === 'window' && rule.windows}
            {#each rule.windows as w}
              <div class="timeline-bar channel" title={ch} style="left: {minuteToPercent(parseHHMM(w.start))}%; width: {minuteToPercent(w.duration_min)}%"></div>
            {/each}
          {/if}
        {/each}
        <div class="timeline-hours">
          {#each Array(24) as _, h}
            <span style="left: {(h / 24) * 100}%">{h}</span>
          {/each}
        </div>
      </div>
    </section>
  {:else}
    <textarea bind:value={jsonText} rows="30" class="json-editor"></textarea>
  {/if}

  <div class="save-bar">
    <button onclick={save} disabled={saving}>{saving ? 'Saving...' : 'Save'}</button>
    <button onclick={() => goto('/recipes')}>Back</button>
  </div>
{/if}

<style>
  .tabs { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .tabs .active { font-weight: bold; text-decoration: underline; }
  section { margin-bottom: 1.5rem; }
  label { display: block; margin: 0.3rem 0; }
  .channel-card { border: 1px solid #444; padding: 0.5rem; margin: 0.5rem 0; border-radius: 4px; }
  .small { font-size: 0.8rem; }
  .save-bar { display: flex; gap: 0.5rem; margin-top: 1rem; }
  .json-editor { width: 100%; font-family: monospace; }
  .error { color: red; }
  .timeline { position: relative; height: 60px; background: #1a1a2e; border-radius: 4px; margin-top: 0.5rem; overflow: hidden; }
  .timeline-bar { position: absolute; height: 20px; border-radius: 2px; }
  .timeline-bar.main { background: #f0c040; top: 5px; opacity: 0.8; }
  .timeline-bar.channel { background: #40a0f0; top: 30px; opacity: 0.7; }
  .timeline-hours { position: absolute; bottom: 0; width: 100%; height: 15px; }
  .timeline-hours span { position: absolute; font-size: 0.6rem; color: #888; }
  .window-entry { margin-left: 1rem; }
</style>
