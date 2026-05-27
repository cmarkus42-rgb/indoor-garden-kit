<script lang="ts">
  import type { RecipeData, ChannelSchedule } from '$lib/types.js';

  interface Props {
    recipe: RecipeData;
    nowMin: number;
    size?: 'lg' | 'md' | 'sm' | 'mini';
  }

  let { recipe, nowMin, size = 'lg' }: Props = $props();

  const SIZES = { lg: 300, md: 200, sm: 140, mini: 80 } as const;
  const STROKE_W = { lg: 14, md: 10, sm: 7, mini: 4 } as const;
  const CHAN_W = { lg: 6, md: 4, sm: 3, mini: 2 } as const;
  const TICK_LEN = { lg: 8, md: 6, sm: 4, mini: 3 } as const;
  const LABEL_SIZE = { lg: 24, md: 16, sm: 11, mini: 0 } as const;
  const CENTER_SIZE = { lg: 24, md: 16, sm: 12, mini: 9 } as const;

  const CHAN_COLORS: Record<string, string> = {
    far_red: 'var(--st-light)',
    dawn: 'var(--st-recipe)',
    uva: 'var(--st-crit)',
    deep_blue: 'var(--st-info)',
  };

  function parseTime(t: string): number {
    const [h, m] = t.split(':').map(Number);
    return h * 60 + (m || 0);
  }

  function polar(min: number, r: number): { x: number; y: number } {
    const angle = ((min / 1440) * 360 - 90) * (Math.PI / 180);
    return { x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) };
  }

  function arc(minA: number, minB: number, r: number): string {
    const pA = polar(minA, r);
    const pB = polar(minB, r);
    let span = minB - minA;
    if (span < 0) span += 1440;
    const large = span > 720 ? 1 : 0;
    return `M ${pA.x} ${pA.y} A ${r} ${r} 0 ${large} 1 ${pB.x} ${pB.y}`;
  }

  let px = $derived(SIZES[size]);
  let cx = $derived(px / 2);
  let cy = $derived(px / 2);
  let outerR = $derived(px / 2 - 2);
  let mainR = $derived(outerR - TICK_LEN[size] - 4);
  let sw = $derived(STROKE_W[size]);
  let chanW = $derived(CHAN_W[size]);

  let onMin = $derived(parseTime(recipe.photoperiod.on));
  let offMin = $derived(parseTime(recipe.photoperiod.off));

  let channelEntries = $derived(
    Object.entries(recipe.channels).map(([name, rule], i) => {
      let chOn = onMin;
      let chOff = offMin;
      if (rule.rule === 'before_on' && rule.offset_min != null && rule.duration_min != null) {
        chOn = (onMin - rule.offset_min + 1440) % 1440;
        chOff = (chOn + rule.duration_min) % 1440;
      } else if (rule.rule === 'after_off' && rule.offset_min != null && rule.duration_min != null) {
        chOn = (offMin + rule.offset_min) % 1440;
        chOff = (chOn + rule.duration_min) % 1440;
      } else if (rule.rule === 'window' && rule.windows?.length) {
        const w = rule.windows[0];
        chOn = parseTime(w.start);
        chOff = (chOn + w.duration_min) % 1440;
      }
      return { name, on: chOn, off: chOff, index: i };
    })
  );

  let nowLabel = $derived(() => {
    const h = Math.floor(nowMin / 60) % 24;
    const m = nowMin % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`;
  });

  // Dimming gradient ID
  let gradId = $derived(`dim-${size}-${onMin}-${offMin}`);

  // Dimming arcs: sunrise (on → on+sunrise_min) and sunset (off-sunset_min → off)
  let sunriseEnd = $derived((onMin + recipe.dimming.sunrise_min) % 1440);
  let sunsetStart = $derived((offMin - recipe.dimming.sunset_min + 1440) % 1440);

  // Hour ticks
  const HOURS = Array.from({ length: 24 }, (_, i) => i);
  const LABEL_HOURS = [0, 6, 12, 18];

  function hourToMin(h: number): number {
    return h * 60;
  }
</script>

<svg
  width={px}
  height={px}
  viewBox="0 0 {px} {px}"
  class="polar-ring polar-ring--{size}"
  role="img"
  aria-label="24h light schedule for {recipe.name}"
>
  <defs>
    <!-- Sunrise gradient: low opacity → high opacity -->
    <linearGradient id="{gradId}-sr" gradientUnits="userSpaceOnUse"
      x1={polar(onMin, mainR).x} y1={polar(onMin, mainR).y}
      x2={polar(sunriseEnd, mainR).x} y2={polar(sunriseEnd, mainR).y}>
      <stop offset="0%" stop-color="var(--st-light)" stop-opacity={recipe.dimming.min_pct / 100} />
      <stop offset="100%" stop-color="var(--st-light)" stop-opacity={recipe.dimming.max_pct / 100} />
    </linearGradient>
    <!-- Sunset gradient: high opacity → low opacity -->
    <linearGradient id="{gradId}-ss" gradientUnits="userSpaceOnUse"
      x1={polar(sunsetStart, mainR).x} y1={polar(sunsetStart, mainR).y}
      x2={polar(offMin, mainR).x} y2={polar(offMin, mainR).y}>
      <stop offset="0%" stop-color="var(--st-light)" stop-opacity={recipe.dimming.max_pct / 100} />
      <stop offset="100%" stop-color="var(--st-light)" stop-opacity={recipe.dimming.min_pct / 100} />
    </linearGradient>
  </defs>

  <!-- (a) 24h hour ticks -->
  {#each HOURS as h}
    {@const min = hourToMin(h)}
    {@const p1 = polar(min, outerR)}
    {@const p2 = polar(min, outerR - TICK_LEN[size])}
    <line
      x1={p1.x} y1={p1.y}
      x2={p2.x} y2={p2.y}
      stroke="var(--ink-4)"
      stroke-width={LABEL_HOURS.includes(h) ? 1.5 : 0.75}
      stroke-linecap="round"
    />
    {#if LABEL_HOURS.includes(h) && LABEL_SIZE[size] > 0}
      {@const pLabel = polar(min, outerR - TICK_LEN[size] - (size === 'lg' ? 12 : 8))}
      <text
        x={pLabel.x}
        y={pLabel.y}
        text-anchor="middle"
        dominant-baseline="central"
        class="tick-label"
        font-size={size === 'lg' ? 11 : 9}
      >
        {String(h).padStart(2, '0')}
      </text>
    {/if}
  {/each}

  <!-- (b) Main photoperiod arc -->
  <path
    d={arc(onMin, offMin, mainR)}
    fill="none"
    stroke="var(--st-light)"
    stroke-width={sw}
    stroke-linecap="round"
    opacity="0.35"
  />

  <!-- (c) Dimming wedges -->
  <!-- Sunrise ramp -->
  <path
    d={arc(onMin, sunriseEnd, mainR)}
    fill="none"
    stroke="url(#{gradId}-sr)"
    stroke-width={sw}
    stroke-linecap="round"
  />
  <!-- Full brightness middle -->
  <path
    d={arc(sunriseEnd, sunsetStart, mainR)}
    fill="none"
    stroke="var(--st-light)"
    stroke-width={sw}
    stroke-linecap="round"
    opacity={recipe.dimming.max_pct / 100}
  />
  <!-- Sunset ramp -->
  <path
    d={arc(sunsetStart, offMin, mainR)}
    fill="none"
    stroke="url(#{gradId}-ss)"
    stroke-width={sw}
    stroke-linecap="round"
  />

  <!-- (d) Channel rings -->
  {#each channelEntries as ch}
    {@const r = mainR - sw / 2 - 4 - ch.index * (chanW + 2)}
    {@const color = CHAN_COLORS[ch.name] ?? 'var(--accent)'}
    <path
      d={arc(ch.on, ch.off, r)}
      fill="none"
      stroke={color}
      stroke-width={chanW}
      stroke-linecap="round"
      opacity="0.8"
    />
  {/each}

  <!-- (e) Now needle -->
  {#each [true] as _}
    {@const needleInner = size === 'mini' ? cx * 0.3 : cx * 0.15}
    {@const pNeedleIn = polar(nowMin, needleInner)}
    {@const pNeedleOut = polar(nowMin, outerR)}
    <line
      x1={pNeedleIn.x} y1={pNeedleIn.y}
      x2={pNeedleOut.x} y2={pNeedleOut.y}
      stroke="var(--ink-1)"
      stroke-width="2"
      stroke-linecap="round"
    />
    <!-- Needle tip dot -->
    <circle
      cx={pNeedleOut.x}
      cy={pNeedleOut.y}
      r={size === 'lg' ? 3 : 2}
      fill="var(--ink-1)"
    />
  {/each}

  <!-- (f) Center time -->
  {#if size !== 'mini'}
    <text
      x={cx}
      y={cy}
      text-anchor="middle"
      dominant-baseline="central"
      class="center-time"
      font-size={CENTER_SIZE[size]}
    >
      {nowLabel()}
    </text>
  {/if}
</svg>

<style>
  .polar-ring {
    display: block;
    flex-shrink: 0;
  }

  .tick-label {
    font-family: var(--font-mono);
    fill: var(--ink-4);
    letter-spacing: 0.04em;
  }

  .center-time {
    font-family: var(--font-mono);
    font-weight: 500;
    fill: var(--ink-1);
    letter-spacing: 0.06em;
  }
</style>
