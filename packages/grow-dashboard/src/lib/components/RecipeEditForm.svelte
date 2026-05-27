<script lang="ts">
  import type { RecipeData, DimmingConfig } from '$lib/types.js';
  import ValueCard from './ValueCard.svelte';

  interface Props {
    recipe: RecipeData;
    original: RecipeData;
    onUpdate: (recipe: RecipeData) => void;
  }

  let { recipe, original, onUpdate }: Props = $props();

  /* ---------- time helpers ---------- */

  function parseTime(t: string): { h: number; m: number } {
    const [h, m] = t.split(':').map(Number);
    return { h, m: m ?? 0 };
  }

  function formatTime(h: number, m: number): string {
    return `${String(((h % 24) + 24) % 24).padStart(2, '0')}:${String(((m % 60) + 60) % 60).padStart(2, '0')}`;
  }

  function stepTime(time: string, field: 'h' | 'm', delta: number): string {
    const t = parseTime(time);
    if (field === 'h') t.h = ((t.h + delta) % 24 + 24) % 24;
    else t.m = ((t.m + delta * 5) % 60 + 60) % 60;
    return formatTime(t.h, t.m);
  }

  /* ---------- derived state ---------- */

  let onTime = $derived(parseTime(recipe.photoperiod.on));
  let offTime = $derived(parseTime(recipe.photoperiod.off));
  let origOnTime = $derived(parseTime(original.photoperiod.on));
  let origOffTime = $derived(parseTime(original.photoperiod.off));

  let dirtyOnH = $derived(onTime.h !== origOnTime.h);
  let dirtyOnM = $derived(onTime.m !== origOnTime.m);
  let dirtyOffH = $derived(offTime.h !== origOffTime.h);
  let dirtyOffM = $derived(offTime.m !== origOffTime.m);

  let dirtySunrise = $derived(recipe.dimming.sunrise_min !== original.dimming.sunrise_min);
  let dirtySunset = $derived(recipe.dimming.sunset_min !== original.dimming.sunset_min);
  let dirtyMax = $derived(recipe.dimming.max_pct !== original.dimming.max_pct);
  let dirtyMin = $derived(recipe.dimming.min_pct !== original.dimming.min_pct);

  /* ---------- validation ---------- */

  let errPhotoperiod = $derived(
    recipe.photoperiod.on === recipe.photoperiod.off ? 'On und Off duerfen nicht gleich sein' : ''
  );
  let errMaxMin = $derived(
    recipe.dimming.max_pct <= recipe.dimming.min_pct ? 'Max muss groesser als Min sein' : ''
  );
  let errSunrise = $derived(
    recipe.dimming.sunrise_min < 0 || recipe.dimming.sunrise_min > 120 ? '0–120 min' : ''
  );
  let errSunset = $derived(
    recipe.dimming.sunset_min < 0 || recipe.dimming.sunset_min > 120 ? '0–120 min' : ''
  );

  /* ---------- updaters ---------- */

  function updateOn(field: 'h' | 'm', delta: number) {
    onUpdate({
      ...recipe,
      photoperiod: { ...recipe.photoperiod, on: stepTime(recipe.photoperiod.on, field, delta) },
    });
  }

  function updateOff(field: 'h' | 'm', delta: number) {
    onUpdate({
      ...recipe,
      photoperiod: { ...recipe.photoperiod, off: stepTime(recipe.photoperiod.off, field, delta) },
    });
  }

  function updateDimming(key: keyof DimmingConfig, delta: number) {
    const clamp = (v: number, min: number, max: number) => Math.max(min, Math.min(max, v));
    const limits: Record<keyof DimmingConfig, [number, number]> = {
      sunrise_min: [0, 120],
      sunset_min: [0, 120],
      max_pct: [0, 100],
      min_pct: [0, 100],
    };
    const [lo, hi] = limits[key];
    const step = key.endsWith('_pct') ? 5 : 1;
    onUpdate({
      ...recipe,
      dimming: { ...recipe.dimming, [key]: clamp(recipe.dimming[key] + delta * step, lo, hi) },
    });
  }
</script>

<section class="edit-form">
  <h3 class="section-title">Photoperiode</h3>
  {#if errPhotoperiod}
    <p class="section-error">{errPhotoperiod}</p>
  {/if}
  <div class="card-row">
    <ValueCard
      value={String(onTime.h).padStart(2, '0')}
      unit="h"
      label="ON HOUR"
      dirty={dirtyOnH}
      sub={dirtyOnH ? `war ${String(origOnTime.h).padStart(2, '0')}` : undefined}
      error={errPhotoperiod ? ' ' : undefined}
      onStep={(d) => updateOn('h', d)}
    />
    <ValueCard
      value={String(onTime.m).padStart(2, '0')}
      unit="min"
      label="ON MIN"
      dirty={dirtyOnM}
      sub={dirtyOnM ? `war ${String(origOnTime.m).padStart(2, '0')}` : undefined}
      onStep={(d) => updateOn('m', d)}
    />
    <ValueCard
      value={String(offTime.h).padStart(2, '0')}
      unit="h"
      label="OFF HOUR"
      dirty={dirtyOffH}
      sub={dirtyOffH ? `war ${String(origOffTime.h).padStart(2, '0')}` : undefined}
      error={errPhotoperiod ? ' ' : undefined}
      onStep={(d) => updateOff('h', d)}
    />
    <ValueCard
      value={String(offTime.m).padStart(2, '0')}
      unit="min"
      label="OFF MIN"
      dirty={dirtyOffM}
      sub={dirtyOffM ? `war ${String(origOffTime.m).padStart(2, '0')}` : undefined}
      onStep={(d) => updateOff('m', d)}
    />
  </div>

  <h3 class="section-title">Dimming</h3>
  <div class="card-row">
    <ValueCard
      value={recipe.dimming.sunrise_min}
      unit="min"
      label="SUNRISE"
      dirty={dirtySunrise}
      sub={dirtySunrise ? `war ${original.dimming.sunrise_min}` : undefined}
      error={errSunrise || undefined}
      onStep={(d) => updateDimming('sunrise_min', d)}
    />
    <ValueCard
      value={recipe.dimming.sunset_min}
      unit="min"
      label="SUNSET"
      dirty={dirtySunset}
      sub={dirtySunset ? `war ${original.dimming.sunset_min}` : undefined}
      error={errSunset || undefined}
      onStep={(d) => updateDimming('sunset_min', d)}
    />
    <ValueCard
      value={recipe.dimming.max_pct}
      unit="%"
      label="MAX"
      dirty={dirtyMax}
      sub={dirtyMax ? `war ${original.dimming.max_pct}` : undefined}
      error={errMaxMin || undefined}
      onStep={(d) => updateDimming('max_pct', d)}
    />
    <ValueCard
      value={recipe.dimming.min_pct}
      unit="%"
      label="MIN"
      dirty={dirtyMin}
      sub={dirtyMin ? `war ${original.dimming.min_pct}` : undefined}
      error={errMaxMin || undefined}
      onStep={(d) => updateDimming('min_pct', d)}
    />
  </div>
</section>

<style>
  .edit-form {
    display: flex;
    flex-direction: column;
    gap: var(--s-6);
  }

  .section-title {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin: 0;
  }

  .section-error {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--st-crit);
    margin: var(--s-1) 0 0;
  }

  .card-row {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
    gap: var(--s-3);
    margin-top: var(--s-2);
  }
</style>
