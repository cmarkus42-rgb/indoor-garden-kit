<script lang="ts">
  import uPlot from 'uplot';
  import 'uplot/dist/uPlot.min.css';
  import { onMount } from 'svelte';

  interface Props {
    data: uPlot.AlignedData;
    series: uPlot.Series[];
    height?: number;
    hooks?: uPlot.Hooks.Arrays;
    bands?: uPlot.Band[];
    scales?: Record<string, uPlot.Scale>;
    axes?: uPlot.Axis[];
    onready?: (chart: uPlot) => void;
    ondestroy?: () => void;
  }

  let {
    data,
    series,
    height = 200,
    hooks,
    bands,
    scales,
    axes,
    onready,
    ondestroy
  }: Props = $props();

  let container: HTMLDivElement | undefined = $state();
  let tooltipEl: HTMLDivElement | undefined = $state();
  let chart: uPlot | null = null;
  let tooltipVisible = $state(false);
  let tooltipLeft = $state(0);
  let tooltipTop = $state(0);
  let tooltipHtml = $state('');
  let seriesVisible = $state<boolean[]>([]);

  function getVar(name: string): string {
    if (!container) return '';
    return getComputedStyle(container).getPropertyValue(name).trim();
  }

  function formatTimestamp(unix: number): string {
    const d = new Date(unix * 1000);
    const hh = String(d.getHours()).padStart(2, '0');
    const mm = String(d.getMinutes()).padStart(2, '0');
    const ss = String(d.getSeconds()).padStart(2, '0');
    return `${hh}:${mm}:${ss}`;
  }

  function updateTooltip(u: uPlot): void {
    const idx = u.cursor.idx;
    const left = u.cursor.left ?? -1;
    const top = u.cursor.top ?? -1;

    if (idx == null || left < 0 || top < 0) {
      tooltipVisible = false;
      return;
    }

    const ts = u.data[0][idx];
    if (ts == null) { tooltipVisible = false; return; }

    let html = `<div class="tt-time">${formatTimestamp(ts)}</div>`;

    for (let i = 1; i < u.series.length; i++) {
      const s = u.series[i];
      if (!s.show) continue;

      const val = u.data[i]?.[idx];
      const label = s.label ?? `Series ${i}`;
      const color = typeof s.stroke === 'function' ? (s.stroke(u, i) ?? '#888') : (s.stroke ?? '#888');
      const display = val != null ? val.toFixed(1) : '—';

      html += `<div class="tt-row"><span class="tt-dot" style="background:${color}"></span>${label}: <b>${display}</b></div>`;
    }

    tooltipHtml = html;

    // Position with offset; flip if near right/bottom edge
    const wrap = u.over;
    const ox = left + 14;
    const oy = top - 10;
    const flipX = (ox + 160) > wrap.offsetWidth;
    const flipY = oy < 10;

    tooltipLeft = flipX ? left - 164 : ox;
    tooltipTop = flipY ? top + 14 : oy;
    tooltipVisible = true;
  }

  function toggleSeries(idx: number) {
    if (!chart) return;
    const newShow = !chart.series[idx].show;
    chart.setSeries(idx, { show: newShow });
    seriesVisible = seriesVisible.map((v, i) => i === idx ? newShow : v);
  }

  function buildOpts(w: number): uPlot.Options {
    const ink4 = getVar('--ink-4') || '#5c7160';
    const gridColor = getVar('--grid') || 'oklch(82% 0.14 145 / 0.07)';

    const axisDefaults: uPlot.Axis = {
      stroke: ink4,
      grid: { stroke: gridColor, width: 1 },
      ticks: { stroke: ink4, width: 1, size: 3 },
      font: '10px JetBrains Mono',
      labelFont: '10px JetBrains Mono',
      labelGap: 4,
      gap: 4,
    };

    const defaultAxes: uPlot.Axis[] = [
      { ...axisDefaults },
      { ...axisDefaults },
    ];

    // Merge caller hooks with our setCursor hook
    const callerHooks = hooks ?? {};
    const mergedHooks: uPlot.Hooks.Arrays = { ...callerHooks };
    const setCursorHooks = [...(callerHooks.setCursor ?? []), updateTooltip];
    mergedHooks.setCursor = setCursorHooks;

    return {
      width: w,
      height,
      series,
      hooks: mergedHooks,
      bands,
      scales,
      axes: axes ?? defaultAxes,
      padding: [8, 8, 0, 0],
      legend: { show: false },
      cursor: {
        drag: { x: true, y: false },
        focus: { prox: 16 },
      },
    };
  }

  onMount(() => {
    if (!container) return;

    const w = container.offsetWidth || 600;
    chart = new uPlot(buildOpts(w), data, container);
    onready?.(chart);
    seriesVisible = series.map(() => true);

    const ro = new ResizeObserver(([entry]) => {
      const newW = Math.floor(entry.contentRect.width);
      if (newW > 0 && chart) {
        chart.setSize({ width: newW, height });
      }
    });
    ro.observe(container);

    return () => {
      ro.disconnect();
      ondestroy?.();
      chart?.destroy();
      chart = null;
    };
  });

  $effect(() => {
    const d = data;
    const s = series;
    if (!chart || !container) return;

    // If series count changed, recreate the chart
    if (s.length !== chart.series.length) {
      ondestroy?.();
      chart.destroy();
      const w = container.offsetWidth || 600;
      chart = new uPlot(buildOpts(w), d, container);
      onready?.(chart);
      seriesVisible = s.map(() => true);
      return;
    }

    try {
      chart.setData(d);
    } catch {
      // Corrupted state — recreate
      chart.destroy();
      const w = container.offsetWidth || 600;
      chart = new uPlot(buildOpts(w), d, container);
      onready?.(chart);
      seriesVisible = s.map(() => true);
    }
  });
</script>

<div class="chart-wrap" bind:this={container}>
  {#if tooltipVisible}
    <div
      class="chart-tooltip"
      bind:this={tooltipEl}
      style="left:{tooltipLeft}px;top:{tooltipTop}px"
    >
      {@html tooltipHtml}
    </div>
  {/if}
</div>

{#if series.length > 1}
  <div class="chart-legend">
    {#each series.slice(1) as s, i}
      {@const idx = i + 1}
      {@const color = typeof s.stroke === 'string' ? s.stroke : '#888'}
      <button
        class="legend-item"
        class:legend-hidden={seriesVisible[idx] === false}
        onclick={() => toggleSeries(idx)}
      >
        <span class="legend-dot" style="background:{color}"></span>
        <span class="legend-label">{s.label ?? `Series ${idx}`}</span>
      </button>
    {/each}
  </div>
{/if}

<style>
  .chart-wrap {
    position: relative;
    background: var(--bg-inset);
    border-radius: var(--r-2);
    width: 100%;
    overflow: hidden;
  }

  /* Ensure uPlot canvas fills the wrapper */
  .chart-wrap :global(.uplot),
  .chart-wrap :global(.uplot canvas) {
    display: block;
  }

  /* Floating cursor tooltip */
  .chart-tooltip {
    position: absolute;
    z-index: 10;
    pointer-events: none;
    background: oklch(18% 0.02 145 / 0.92);
    border: 1px solid oklch(40% 0.08 145 / 0.35);
    border-radius: 6px;
    padding: 6px 10px;
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 10px;
    line-height: 1.5;
    color: oklch(88% 0.06 145);
    white-space: nowrap;
    backdrop-filter: blur(6px);
    box-shadow: 0 2px 8px oklch(0% 0 0 / 0.35);
  }

  .chart-tooltip :global(.tt-time) {
    color: oklch(70% 0.04 145);
    margin-bottom: 2px;
    font-size: 9px;
    letter-spacing: 0.03em;
  }

  .chart-tooltip :global(.tt-row) {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .chart-tooltip :global(.tt-dot) {
    display: inline-block;
    width: 8px;
    height: 3px;
    border-radius: 1px;
    flex-shrink: 0;
  }

  .chart-tooltip :global(b) {
    color: oklch(95% 0.08 145);
    font-variant-numeric: tabular-nums;
  }

  .chart-legend {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s-1, 4px) var(--s-3, 12px);
    padding: var(--s-2, 8px) var(--s-2, 8px) var(--s-1, 4px);
  }

  .legend-item {
    display: flex;
    align-items: center;
    gap: 4px;
    background: none;
    border: none;
    cursor: pointer;
    padding: 2px 4px;
    border-radius: 3px;
    font-family: var(--font-mono, 'JetBrains Mono', monospace);
    font-size: 10px;
    color: var(--ink-3, #7a9a7e);
    transition: opacity 0.15s;
  }

  .legend-item:hover {
    background: var(--bg-2, rgba(0,0,0,0.05));
  }

  .legend-hidden {
    opacity: 0.35;
  }

  .legend-dot {
    display: inline-block;
    width: 8px;
    height: 3px;
    border-radius: 1px;
    flex-shrink: 0;
  }

  .legend-label {
    user-select: none;
  }
</style>
