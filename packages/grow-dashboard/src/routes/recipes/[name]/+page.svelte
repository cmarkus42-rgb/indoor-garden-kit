<script lang="ts">
  import { get, put, getGroups } from '$lib/api.js';
  import type { RecipeData, ChannelRule, DeviceGroup, SensorTrigger } from '$lib/types.js';
  import { PRESETS, eodFarRedChannel, dawnDuskChannels, vegSteeringTriggers, genSteeringTriggers, fourPhaseIrrigation } from '$lib/presets.js';
  import PolarRing from '$lib/components/PolarRing.svelte';
  import ValueCard from '$lib/components/ValueCard.svelte';
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { onMount } from 'svelte';

  let recipe = $state<RecipeData | null>(null);
  let jsonText = $state('');
  let activeTab = $state<'visual' | 'json'>('visual');
  let saving = $state(false);
  let error = $state('');
  let copied = $state(false);
  let allGroups = $state<DeviceGroup[]>([]);
  let lightGroups = $state<DeviceGroup[]>([]);
  let channelPickerOpen = $state(false);
  let channelPickerValue = $state('');

  function getNowMin(): number {
    const d = new Date();
    return d.getHours() * 60 + d.getMinutes();
  }
  let nowMin = $state(getNowMin());

  const name = $derived(decodeURIComponent($page.params.name ?? ''));

  async function load() {
    error = '';
    try {
      recipe = await get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`);
      recipe.sensorTriggers = recipe.sensorTriggers ?? [];
      jsonText = JSON.stringify(recipe, null, 2);
    } catch {
      error = 'Recipe not found';
    }
    try {
      const groupsRes = await getGroups();
      allGroups = groupsRes.groups;
      lightGroups = allGroups.filter(g => g.category === 'light');
      if (lightGroups.length > 0) channelPickerValue = lightGroups[0].name;
    } catch { /* no groups yet */ }
  }

  onMount(() => {
    load();
    const tick = setInterval(() => { nowMin = getNowMin(); }, 60_000);
    return () => clearInterval(tick);
  });

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

  function openChannelPicker() {
    if (!recipe) return;
    if (lightGroups.length === 0) {
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

  function removeChannel(ch: string) {
    if (!recipe) return;
    delete recipe.channels[ch];
    recipe = { ...recipe };
  }

  function updateRule(ch: string, rule: ChannelRule['rule']) {
    if (!recipe) return;
    if (rule === 'window') {
      recipe.channels[ch] = { rule, windows: [{ start: '12:00', duration_min: 30 }] };
    } else if (rule === 'after_off') {
      recipe.channels[ch] = { rule, offset_min: 5, duration_min: 15 };
    } else {
      recipe.channels[ch] = { rule, offset_min: 15, duration_min: 30 };
    }
    recipe = { ...recipe };
  }

  async function copyJson() {
    await navigator.clipboard.writeText(jsonText);
    copied = true;
    setTimeout(() => { copied = false; }, 1500);
  }

  function addSensorRule() {
    if (!recipe) return;
    const triggers = recipe.sensorTriggers ?? [];
    triggers.push({ sensorType: 'soil_moisture', operator: 'lt', threshold: 30, targetGroup: '', action: 'on' });
    recipe = { ...recipe, sensorTriggers: triggers };
  }

  function removeSensorRule(idx: number) {
    if (!recipe) return;
    const triggers = [...(recipe.sensorTriggers ?? [])];
    triggers.splice(idx, 1);
    recipe = { ...recipe, sensorTriggers: triggers };
  }

  function updateSensorRule(idx: number, patch: Partial<SensorTrigger>) {
    if (!recipe) return;
    const triggers = [...(recipe.sensorTriggers ?? [])];
    triggers[idx] = { ...triggers[idx], ...patch };
    recipe = { ...recipe, sensorTriggers: triggers };
  }

  function applyPreset(id: string) {
    if (!recipe) return;
    switch (id) {
      case 'eod_far_red':
        recipe.channels = { ...recipe.channels, ...eodFarRedChannel() };
        break;
      case 'dawn_dusk':
        recipe.channels = { ...recipe.channels, ...dawnDuskChannels() };
        break;
      case 'veg_steering':
      case 'gen_steering': {
        const irrigationGroup = allGroups.find(g => g.category === 'irrigation')?.name ?? '';
        if (!irrigationGroup) { window.alert('Create an irrigation group first'); return; }
        const triggers = id === 'veg_steering'
          ? vegSteeringTriggers(irrigationGroup)
          : genSteeringTriggers(irrigationGroup);
        recipe.sensorTriggers = [...(recipe.sensorTriggers ?? []), ...triggers];
        break;
      }
      case 'four_phase': {
        const group = allGroups.find(g => g.category === 'irrigation')?.name ?? '';
        if (!group) { window.alert('Create an irrigation group first'); return; }
        const result = fourPhaseIrrigation(recipe.photoperiod.on, recipe.photoperiod.off, group);
        recipe.channels = { ...recipe.channels, ...result.channels };
        recipe.sensorTriggers = [...(recipe.sensorTriggers ?? []), ...result.triggers];
        break;
      }
    }
    recipe = { ...recipe };
  }

  function stepDimming(key: keyof RecipeData['dimming'], delta: number) {
    if (!recipe) return;
    const max = key === 'max_pct' || key === 'min_pct' ? 100 : 120;
    recipe = {
      ...recipe,
      dimming: {
        ...recipe.dimming,
        [key]: Math.max(0, Math.min(max, recipe.dimming[key] + delta)),
      },
    };
  }
</script>

<div class="page">
  <!-- ── Breadcrumb ── -->
  <nav class="breadcrumb" aria-label="Breadcrumb">
    <a class="bc-link" href="/recipes">RECIPES</a>
    <span class="bc-sep">/</span>
    <span class="bc-current">{name.toUpperCase()}</span>
  </nav>

  {#if error && !recipe}
    <div class="error-banner">{error}</div>
  {/if}

  {#if recipe}
    <div class="layout">
      <!-- ── Left: PolarRing ── -->
      <div class="ring-col">
        <div class="ring-sticky">
          <PolarRing recipe={recipe} nowMin={nowMin} size="lg" />
        </div>
      </div>

      <!-- ── Right: Form ── -->
      <div class="form-col">
        <!-- Tab bar -->
        <div class="tab-bar">
          <button
            class="tab"
            class:tab--active={activeTab === 'visual'}
            onclick={() => activeTab = 'visual'}
          >VISUAL</button>
          <button
            class="tab"
            class:tab--active={activeTab === 'json'}
            onclick={() => { activeTab = 'json'; jsonText = JSON.stringify(recipe, null, 2); }}
          >JSON</button>
        </div>

        {#if activeTab === 'visual'}
          <!-- Photoperiod -->
          <section class="form-section">
            <div class="section-header">
              <span class="section-label">PHOTOPERIOD</span>
            </div>
            <div class="time-row">
              <label class="field">
                <span class="field-label">ON</span>
                <input class="input-time" type="time" bind:value={recipe.photoperiod.on} />
              </label>
              <label class="field">
                <span class="field-label">OFF</span>
                <input class="input-time" type="time" bind:value={recipe.photoperiod.off} />
              </label>
            </div>
          </section>

          <!-- Dimming -->
          <section class="form-section">
            <div class="section-header">
              <span class="section-label">DIMMING</span>
            </div>
            <div class="dimming-grid">
              <div class="dimming-item">
                <ValueCard
                  value={recipe.dimming.sunrise_min}
                  unit="min"
                  label="SUNRISE"
                  onStep={(d) => stepDimming('sunrise_min', d)}
                />
                <input class="slider" type="range" min="0" max="120"
                  bind:value={recipe.dimming.sunrise_min} />
              </div>
              <div class="dimming-item">
                <ValueCard
                  value={recipe.dimming.sunset_min}
                  unit="min"
                  label="SUNSET"
                  onStep={(d) => stepDimming('sunset_min', d)}
                />
                <input class="slider" type="range" min="0" max="120"
                  bind:value={recipe.dimming.sunset_min} />
              </div>
              <div class="dimming-item">
                <ValueCard
                  value={recipe.dimming.max_pct}
                  unit="%"
                  label="MAX"
                  onStep={(d) => stepDimming('max_pct', d)}
                />
                <input class="slider" type="range" min="0" max="100"
                  bind:value={recipe.dimming.max_pct} />
              </div>
              <div class="dimming-item">
                <ValueCard
                  value={recipe.dimming.min_pct}
                  unit="%"
                  label="MIN"
                  onStep={(d) => stepDimming('min_pct', d)}
                />
                <input class="slider" type="range" min="0" max="100"
                  bind:value={recipe.dimming.min_pct} />
              </div>
            </div>
          </section>

          <!-- Channels -->
          <section class="form-section">
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

            {#if Object.keys(recipe.channels).length === 0}
              <p class="empty-msg">No channels defined</p>
            {:else}
              <div class="channels-list">
                {#each Object.entries(recipe.channels) as [ch, rule]}
                  <div class="channel-card">
                    <div class="channel-header">
                      <span class="channel-name">{ch}</span>
                      <select
                        class="input-select-sm"
                        value={rule.rule}
                        onchange={(e) => updateRule(ch, (e.target as HTMLSelectElement).value as ChannelRule['rule'])}
                      >
                        <option value="before_on">before_on</option>
                        <option value="after_off">after_off</option>
                        <option value="window">window</option>
                      </select>
                      <button class="btn-remove" onclick={() => removeChannel(ch)} aria-label="Remove {ch}">
                        <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                          <line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                          <line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                      </button>
                    </div>

                    {#if rule.rule === 'before_on' || rule.rule === 'after_off'}
                      <div class="channel-fields">
                        <label class="field-inline">
                          <span class="field-label-sm">OFFSET</span>
                          <input class="input-num-sm" type="number" bind:value={rule.offset_min} min="0" />
                          <span class="field-unit">min</span>
                        </label>
                        <label class="field-inline">
                          <span class="field-label-sm">DURATION</span>
                          <input class="input-num-sm" type="number" bind:value={rule.duration_min} min="0" />
                          <span class="field-unit">min</span>
                        </label>
                      </div>
                    {/if}

                    {#if rule.rule === 'window' && rule.windows}
                      {#each rule.windows as w}
                        <div class="channel-fields">
                          <label class="field-inline">
                            <span class="field-label-sm">START</span>
                            <input class="input-time-sm" type="time" bind:value={w.start} />
                          </label>
                          <label class="field-inline">
                            <span class="field-label-sm">DURATION</span>
                            <input class="input-num-sm" type="number" bind:value={w.duration_min} min="1" />
                            <span class="field-unit">min</span>
                          </label>
                        </div>
                      {/each}
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </section>

          <!-- Presets -->
          <section class="form-section">
            <div class="section-header">
              <span class="section-label">PRESETS</span>
            </div>
            <div class="preset-grid">
              {#each PRESETS as p (p.id)}
                <div class="preset-card">
                  <div class="preset-top">
                    <span class="preset-name">{p.label}</span>
                    <span class="preset-chip" class:preset-chip--light={p.category === 'light'} class:preset-chip--irrigation={p.category === 'irrigation'}>{p.category}</span>
                  </div>
                  <p class="preset-desc">{p.description}</p>
                  <button class="btn-ghost-sm" onclick={() => applyPreset(p.id)}>Apply</button>
                </div>
              {/each}
            </div>
          </section>

          <!-- Sensor Rules -->
          <section class="form-section">
            <div class="section-header">
              <span class="section-label">SENSOR RULES</span>
              <button class="btn-ghost-sm" onclick={addSensorRule}>+ Add Rule</button>
            </div>

            {#if (recipe.sensorTriggers ?? []).length === 0}
              <p class="empty-msg">No sensor rules defined</p>
            {:else}
              <div class="channels-list">
                {#each recipe.sensorTriggers ?? [] as trigger, idx}
                  <div class="channel-card">
                    <div class="channel-header">
                      <select
                        class="input-select-sm"
                        value={trigger.sensorType}
                        onchange={(e) => updateSensorRule(idx, { sensorType: (e.target as HTMLSelectElement).value as SensorTrigger['sensorType'] })}
                      >
                        <option value="soil_moisture">Soil Moisture</option>
                        <option value="temperature">Temperature</option>
                        <option value="humidity">Humidity</option>
                        <option value="vpd">VPD</option>
                      </select>
                      <select
                        class="input-select-sm"
                        value={trigger.operator}
                        onchange={(e) => updateSensorRule(idx, { operator: (e.target as HTMLSelectElement).value as SensorTrigger['operator'] })}
                      >
                        <option value="lt">&lt; below</option>
                        <option value="gt">&gt; above</option>
                        <option value="between">range</option>
                      </select>
                      <button class="btn-remove" onclick={() => removeSensorRule(idx)} aria-label="Remove rule">
                        <svg width="11" height="11" viewBox="0 0 11 11" fill="none">
                          <line x1="2" y1="2" x2="9" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                          <line x1="9" y1="2" x2="2" y2="9" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
                        </svg>
                      </button>
                    </div>

                    <div class="channel-fields">
                      <label class="field-inline">
                        <span class="field-label-sm">THRESHOLD</span>
                        <input class="input-num-sm" type="number" value={trigger.threshold}
                          onchange={(e) => updateSensorRule(idx, { threshold: Number((e.target as HTMLInputElement).value) })} />
                      </label>
                      {#if trigger.operator === 'between'}
                        <label class="field-inline">
                          <span class="field-label-sm">HIGH</span>
                          <input class="input-num-sm" type="number" value={trigger.thresholdHigh ?? 0}
                            onchange={(e) => updateSensorRule(idx, { thresholdHigh: Number((e.target as HTMLInputElement).value) })} />
                        </label>
                      {/if}
                    </div>

                    <div class="channel-fields">
                      <label class="field-inline">
                        <span class="field-label-sm">TARGET</span>
                        <select
                          class="input-select-sm"
                          value={trigger.targetGroup}
                          onchange={(e) => updateSensorRule(idx, { targetGroup: (e.target as HTMLSelectElement).value })}
                        >
                          <option value="">— select group —</option>
                          {#each allGroups as g (g.id)}
                            <option value={g.name}>{g.name}</option>
                          {/each}
                        </select>
                      </label>
                      <label class="field-inline">
                        <span class="field-label-sm">ACTION</span>
                        <select
                          class="input-select-sm"
                          value={trigger.action}
                          onchange={(e) => updateSensorRule(idx, { action: (e.target as HTMLSelectElement).value as SensorTrigger['action'] })}
                        >
                          <option value="on">ON</option>
                          <option value="off">OFF</option>
                          <option value="set_level">Set Level</option>
                        </select>
                      </label>
                      {#if trigger.action === 'set_level'}
                        <label class="field-inline">
                          <span class="field-label-sm">LEVEL</span>
                          <input class="input-num-sm" type="number" min="0" max="100"
                            value={trigger.level ?? 50}
                            onchange={(e) => updateSensorRule(idx, { level: Number((e.target as HTMLInputElement).value) })} />
                          <span class="field-unit">%</span>
                        </label>
                      {/if}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </section>

        {:else}
          <!-- JSON tab -->
          <div class="form-section json-section">
            <div class="section-header">
              <span class="section-label">JSON</span>
              <button class="btn-ghost-sm" onclick={copyJson}>
                {copied ? '✓ Copied' : 'Copy'}
              </button>
            </div>
            <textarea class="json-area" readonly rows="28" value={jsonText}></textarea>
          </div>
        {/if}

        {#if error}
          <div class="error-inline">{error}</div>
        {/if}
      </div>
    </div>
  {/if}
</div>

<!-- ── Sticky save bar ── -->
{#if recipe}
  <div class="save-bar">
    <button class="btn-back" onclick={() => goto('/recipes')}>
      <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
        <path d="M7.5 2L2 6.5l5.5 4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      Recipes
    </button>
    <div class="save-spacer"></div>
    <button class="btn-save" onclick={save} disabled={saving}>
      {saving ? 'Saving…' : 'Save Recipe'}
    </button>
  </div>
{/if}

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    padding-bottom: 72px;
  }

  /* ── Breadcrumb ── */
  .breadcrumb {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .bc-link {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.12em;
    text-decoration: none;
    transition: color 0.1s;
  }

  .bc-link:hover { color: var(--ink-1); }

  .bc-sep {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
  }

  .bc-current {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-1);
    letter-spacing: 0.12em;
  }

  .error-banner {
    background: var(--st-crit-soft);
    border: 1px solid var(--st-crit);
    border-radius: var(--r-2);
    padding: var(--s-3) var(--s-4);
    font: 400 var(--t-12) var(--font-mono);
    color: var(--st-crit);
  }

  .error-inline {
    font: 400 var(--t-11) var(--font-mono);
    color: var(--st-crit);
    padding: var(--s-2) 0;
  }

  /* ── Layout ── */
  .layout {
    display: grid;
    grid-template-columns: 60% 1fr;
    gap: var(--s-6);
    align-items: start;
  }

  .ring-col {
    display: flex;
    justify-content: center;
  }

  .ring-sticky {
    position: sticky;
    top: calc(48px + var(--s-4));
  }

  .form-col {
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  /* ── Tabs ── */
  .tab-bar {
    display: flex;
    border-bottom: 1px solid var(--line);
  }

  .tab {
    padding: var(--s-2) var(--s-4);
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.1em;
    background: transparent;
    border: none;
    border-bottom: 2px solid transparent;
    margin-bottom: -1px;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }

  .tab:hover { color: var(--ink-1); }

  .tab--active {
    color: var(--ink-1);
    border-bottom-color: var(--accent);
  }

  /* ── Sections ── */
  .form-section {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .section-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding-bottom: var(--s-3);
    border-bottom: 1px solid var(--line);
  }

  .section-label {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.14em;
    text-transform: uppercase;
  }

  /* ── Photoperiod ── */
  .time-row {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-3);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .field-label {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.12em;
    text-transform: uppercase;
  }

  .input-time {
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

  .input-time:focus { outline: none; border-color: var(--accent-line); }

  /* ── Dimming ── */
  .dimming-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-3);
  }

  .dimming-item {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .slider {
    width: 100%;
    accent-color: var(--accent);
    cursor: pointer;
    height: 3px;
  }

  /* ── Channels ── */
  .channels-list {
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .channel-card {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .channel-header {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .channel-name {
    font: 600 var(--t-12) var(--font-mono);
    color: var(--ink-1);
    letter-spacing: 0.04em;
    flex: 1;
  }

  .input-select-sm {
    background: var(--bg-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-2);
    font: 400 var(--t-10) var(--font-mono);
    padding: 2px var(--s-2);
    cursor: pointer;
  }

  .input-select-sm:focus { outline: none; border-color: var(--accent-line); }

  .btn-remove {
    display: grid;
    place-items: center;
    width: 22px;
    height: 22px;
    background: transparent;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-4);
    cursor: pointer;
    flex-shrink: 0;
    transition: background 0.1s, color 0.1s, border-color 0.1s;
  }

  .btn-remove:hover {
    background: var(--st-crit-soft);
    border-color: var(--st-crit);
    color: var(--st-crit);
  }

  .channel-fields {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-3);
  }

  .field-inline {
    display: flex;
    align-items: center;
    gap: var(--s-1);
  }

  .field-label-sm {
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    white-space: nowrap;
  }

  .field-unit {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-4);
  }

  .input-num-sm {
    width: 64px;
    background: var(--bg-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font: 400 var(--t-11) var(--font-mono);
    padding: 2px var(--s-2);
    box-sizing: border-box;
  }

  .input-num-sm:focus { outline: none; border-color: var(--accent-line); }

  .input-time-sm {
    background: var(--bg-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font: 400 var(--t-11) var(--font-mono);
    padding: 2px var(--s-2);
  }

  .input-time-sm:focus { outline: none; border-color: var(--accent-line); }

  /* ── JSON tab ── */
  .json-section { gap: var(--s-3); }

  .json-area {
    width: 100%;
    background: var(--bg-inset);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    color: var(--ink-2);
    font: 400 var(--t-10) var(--font-mono);
    padding: var(--s-3);
    resize: vertical;
    box-sizing: border-box;
    letter-spacing: 0.02em;
    line-height: 1.6;
  }

  /* ── Save bar ── */
  .save-bar {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-3) var(--s-6);
    background: var(--bg-0);
    border-top: 1px solid var(--line);
    z-index: 50;
  }

  .save-spacer { flex: 1; }

  .btn-back {
    display: inline-flex;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-4);
    border: 1px solid var(--line-strong);
    border-radius: var(--r-2);
    background: transparent;
    color: var(--ink-3);
    font: 400 var(--t-11) var(--font-mono);
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: color 0.15s, border-color 0.15s;
  }

  .btn-back:hover { color: var(--ink-1); border-color: var(--ink-3); }

  .btn-save {
    display: inline-flex;
    align-items: center;
    padding: var(--s-2) var(--s-6);
    border: none;
    border-radius: var(--r-2);
    background: var(--accent);
    color: var(--bg-0);
    font: 600 var(--t-12) var(--font-mono);
    letter-spacing: 0.08em;
    cursor: pointer;
    transition: opacity 0.15s;
  }

  .btn-save:hover { opacity: 0.85; }
  .btn-save:disabled { opacity: 0.4; cursor: not-allowed; }

  /* ── Shared buttons ── */
  .btn-ghost-sm {
    display: inline-flex;
    align-items: center;
    gap: var(--s-1);
    padding: 2px var(--s-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    background: transparent;
    color: var(--ink-3);
    font: 400 var(--t-10) var(--font-mono);
    letter-spacing: 0.06em;
    cursor: pointer;
    transition: background 0.1s, color 0.1s, border-color 0.1s;
  }

  .btn-ghost-sm:hover {
    background: var(--bg-3);
    color: var(--ink-1);
    border-color: var(--line-strong);
  }

  .empty-msg {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-4);
    padding: var(--s-2) 0;
    margin: 0;
  }

  /* ── Presets ── */
  .preset-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-2);
  }

  .preset-card {
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .preset-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-2);
  }

  .preset-name {
    font: 600 var(--t-11) var(--font-mono);
    color: var(--ink-1);
    letter-spacing: 0.04em;
  }

  .preset-chip {
    font: 500 var(--t-9) var(--font-mono);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    padding: 1px var(--s-2);
    border-radius: var(--r-1);
    white-space: nowrap;
  }

  .preset-chip--light {
    background: var(--accent-soft, rgba(99, 102, 241, 0.12));
    color: var(--accent);
  }

  .preset-chip--irrigation {
    background: var(--st-ok-soft, rgba(34, 197, 94, 0.12));
    color: var(--st-ok);
  }

  .preset-desc {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    margin: 0;
    line-height: 1.4;
  }

  /* ── Channel picker ── */
  .channel-picker {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }
</style>
