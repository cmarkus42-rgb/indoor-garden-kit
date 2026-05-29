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
  let chart: uPlot | null = null;

  function getVar(name: string): string {
    if (!container) return '';
    return getComputedStyle(container).getPropertyValue(name).trim();
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

    return {
      width: w,
      height,
      series,
      hooks: hooks ?? {},
      bands,
      scales,
      axes: axes ?? defaultAxes,
      padding: [8, 8, 0, 0],
      legend: { show: true, live: true },
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
    }
  });
</script>

<div class="chart-wrap" bind:this={container}></div>

<style>
  .chart-wrap {
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

  /* Style the built-in legend */
  .chart-wrap :global(.u-legend) {
    font-family: 'JetBrains Mono', ui-monospace, monospace;
    font-size: 10px;
    color: var(--ink-3);
    padding: 4px 10px 6px;
    background: transparent;
    border-top: 1px solid var(--line);
    display: flex;
    flex-wrap: wrap;
    gap: 2px 12px;
  }

  .chart-wrap :global(.u-legend tr) {
    display: flex;
    align-items: center;
    gap: 5px;
  }

  .chart-wrap :global(.u-legend .u-label) {
    color: var(--ink-3);
  }

  .chart-wrap :global(.u-legend .u-value) {
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
  }

  .chart-wrap :global(.u-legend .u-marker) {
    width: 10px;
    height: 2px;
    border-radius: 1px;
    flex-shrink: 0;
  }
</style>
