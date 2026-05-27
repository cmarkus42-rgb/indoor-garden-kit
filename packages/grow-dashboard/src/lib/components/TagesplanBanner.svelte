<script lang="ts">
  import type { RecipeData, DayPlanResponse } from '$lib/types.js';

  interface Props {
    recipe: RecipeData;
    dayPlan: DayPlanResponse;
    nowMin: number;
  }

  let { recipe, dayPlan, nowMin }: Props = $props();

  const CHAN_COLORS: Record<string, string> = {
    far_red: 'var(--st-light)',
    dawn: 'var(--st-recipe)',
    uva: 'var(--st-crit)',
    deep_blue: 'var(--st-info)',
  };

  const HOUR_LABELS = [0, 3, 6, 9, 12, 15, 18, 21];
  const LANE_H = 20;
  const MAIN_H = 48;

  function pct(min: number): number {
    return (min / 1440) * 100;
  }

  function fmtHour(h: number): string {
    return String(h).padStart(2, '0');
  }

  function fmtTime(min: number): string {
    const h = Math.floor(min / 60) % 24;
    const m = min % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  }

  let nowPct = $derived(pct(nowMin));

  // Build dimming SVG path for the main lane
  // dimming_curve is an array of {time, pct} points
  let dimmingPath = $derived(() => {
    if (!dayPlan.dimming_curve?.length) return '';
    const points = dayPlan.dimming_curve;
    const w = 1000; // viewBox width for inline SVG
    const h = MAIN_H;
    return points
      .map((p, i) => {
        const x = (p.time / 1440) * w;
        const y = h - (p.pct / 100) * h;
        return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
      })
      .join(' ');
  });

  // Create a fill polygon for the dimming area
  let dimmingFill = $derived(() => {
    if (!dayPlan.dimming_curve?.length) return '';
    const points = dayPlan.dimming_curve;
    const w = 1000;
    const h = MAIN_H;
    const path = points.map((p) => {
      const x = (p.time / 1440) * w;
      const y = h - (p.pct / 100) * h;
      return `${x},${y}`;
    });
    const first = (points[0].time / 1440) * w;
    const last = (points[points.length - 1].time / 1440) * w;
    return `${first},${h} ${path.join(' ')} ${last},${h}`;
  });

  let totalHeight = $derived(MAIN_H + dayPlan.channels.length * LANE_H + 32);
</script>

<div class="banner" style="height: {totalHeight}px">
  <!-- X-axis hour labels -->
  <div class="hours">
    {#each HOUR_LABELS as h}
      <span class="hour-label" style="left: {pct(h * 60)}%">{fmtHour(h)}</span>
    {/each}
  </div>

  <!-- Main SANlight lane -->
  <div class="lane lane--main" style="height: {MAIN_H}px">
    <span class="lane-label">Main</span>
    <!-- Active photoperiod block -->
    {#if dayPlan.main_on < dayPlan.main_off}
      <div
        class="block block--main"
        style="left: {pct(dayPlan.main_on)}%; width: {pct(dayPlan.main_off - dayPlan.main_on)}%"
      >
        <!-- Dimming curve overlay -->
        {#if dayPlan.dimming_curve?.length}
          <svg
            class="dimming-svg"
            viewBox="0 0 1000 {MAIN_H}"
            preserveAspectRatio="none"
          >
            <polygon
              points={dimmingFill()}
              fill="var(--st-light)"
              opacity="0.25"
            />
            <polyline
              points={dayPlan.dimming_curve.map(p => `${(p.time / 1440) * 1000},${MAIN_H - (p.pct / 100) * MAIN_H}`).join(' ')}
              fill="none"
              stroke="var(--st-light)"
              stroke-width="2"
              opacity="0.7"
            />
          </svg>
        {/if}
      </div>
    {:else}
      <!-- Wraps midnight -->
      <div
        class="block block--main"
        style="left: {pct(dayPlan.main_on)}%; width: {pct(1440 - dayPlan.main_on)}%"
      ></div>
      <div
        class="block block--main"
        style="left: 0; width: {pct(dayPlan.main_off)}%"
      ></div>
    {/if}
  </div>

  <!-- Channel lanes -->
  {#each dayPlan.channels as ch}
    {@const color = CHAN_COLORS[ch.channel] ?? 'var(--accent)'}
    <div class="lane lane--channel" style="height: {LANE_H}px">
      <span class="lane-label lane-label--sm">{ch.channel}</span>
      {#if ch.on_time < ch.off_time}
        <div
          class="block"
          style="left: {pct(ch.on_time)}%; width: {pct(ch.off_time - ch.on_time)}%; background: {color}; opacity: 0.55"
        ></div>
      {:else}
        <div
          class="block"
          style="left: {pct(ch.on_time)}%; width: {pct(1440 - ch.on_time)}%; background: {color}; opacity: 0.55"
        ></div>
        <div
          class="block"
          style="left: 0; width: {pct(ch.off_time)}%; background: {color}; opacity: 0.55"
        ></div>
      {/if}
    </div>
  {/each}

  <!-- Now marker -->
  <div class="now-marker" style="left: {nowPct}%">
    <span class="now-label">{fmtTime(nowMin)}</span>
    <div class="now-line"></div>
  </div>
</div>

<style>
  .banner {
    position: relative;
    width: 100%;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
    padding-top: 24px;
  }

  .hours {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 24px;
    pointer-events: none;
  }

  .hour-label {
    position: absolute;
    transform: translateX(-50%);
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    letter-spacing: 0.04em;
    top: 6px;
  }

  .lane {
    position: relative;
    width: 100%;
    background: var(--bg-inset);
    border-bottom: 1px solid var(--line);
  }

  .lane--main {
    /* slightly taller, already handled by inline style */
  }

  .lane-label {
    position: absolute;
    left: var(--s-2);
    top: 50%;
    transform: translateY(-50%);
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    letter-spacing: 0.08em;
    text-transform: uppercase;
    z-index: 2;
    pointer-events: none;
  }

  .lane-label--sm {
    font-size: var(--t-9);
    letter-spacing: 0.06em;
  }

  .block {
    position: absolute;
    top: 0;
    height: 100%;
    border-radius: 0;
  }

  .block--main {
    background: var(--st-light-soft);
  }

  .dimming-svg {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .now-marker {
    position: absolute;
    top: 0;
    bottom: 0;
    width: 0;
    z-index: 10;
  }

  .now-line {
    position: absolute;
    top: 0;
    bottom: 0;
    left: 0;
    width: 2px;
    background: var(--ink-1);
    transform: translateX(-1px);
  }

  .now-label {
    position: absolute;
    top: 2px;
    left: 4px;
    font: 500 var(--t-9) var(--font-mono);
    color: var(--ink-1);
    letter-spacing: 0.04em;
    white-space: nowrap;
    background: var(--bg-1);
    padding: 1px 4px;
    border-radius: var(--r-1);
    border: 1px solid var(--line);
  }
</style>
