<script lang="ts">
  import StatusDot from './StatusDot.svelte';

  type TileStatus = 'ok' | 'warn' | 'crit' | 'offline';

  interface Props {
    label: string;
    sub?: string;
    metric: string;
    unit: string;
    status: TileStatus;
    sparklinePoints?: number[];
  }

  const { label, sub, metric, unit, status, sparklinePoints }: Props = $props();

  const dotVariant = $derived<'ok' | 'warn' | 'crit'>(
    status === 'offline' ? 'crit' : status
  );

  const polylinePoints = $derived(() => {
    const pts = sparklinePoints;
    if (!pts || pts.length < 2) return '';
    const w = 50;
    const h = 20;
    const min = Math.min(...pts);
    const max = Math.max(...pts);
    const range = max - min || 1;
    return pts
      .map((v, i) => {
        const x = (i / (pts.length - 1)) * w;
        const y = h - ((v - min) / range) * (h - 2) - 1;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      })
      .join(' ');
  });
</script>

<div class="tile" class:offline={status === 'offline'} data-status={status}>
  {#if status === 'offline'}
    <div class="offline-overlay" aria-hidden="true"></div>
  {/if}

  <div class="tile-header">
    <div class="tile-labels">
      <span class="tile-label">{label}</span>
      {#if sub}
        <span class="tile-sub">{sub}</span>
      {/if}
    </div>
    <StatusDot variant={dotVariant} live={status === 'ok'} />
  </div>

  <div class="tile-body">
    <div class="tile-metric-row">
      <span class="tile-metric">{metric}</span>
      <span class="tile-unit">{unit}</span>
    </div>
    {#if sparklinePoints && sparklinePoints.length >= 2}
      <svg class="sparkline" viewBox="0 0 50 20" width="50" height="20" aria-hidden="true">
        <polyline
          points={polylinePoints()}
          fill="none"
          stroke="var(--accent)"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    {/if}
  </div>
</div>

<style>
  .tile {
    position: relative;
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-3) var(--s-4);
    overflow: hidden;
  }

  .tile.offline {
    opacity: 0.7;
  }

  .offline-overlay {
    position: absolute;
    inset: 0;
    background-image: repeating-linear-gradient(
      135deg,
      transparent,
      transparent 6px,
      var(--line) 6px,
      var(--line) 7px
    );
    pointer-events: none;
    z-index: 1;
  }

  .tile-header {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--s-2);
  }

  .tile-labels {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .tile-label {
    font-size: var(--t-12);
    color: var(--ink-1);
    font-family: var(--font-sans);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tile-sub {
    font-size: var(--t-9);
    color: var(--ink-3);
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tile-body {
    display: flex;
    align-items: flex-end;
    justify-content: space-between;
    gap: var(--s-2);
  }

  .tile-metric-row {
    display: flex;
    align-items: baseline;
    gap: 3px;
  }

  .tile-metric {
    font-family: var(--font-mono);
    font-size: var(--t-20);
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
    line-height: 1;
  }

  .tile-unit {
    font-size: var(--t-10);
    color: var(--ink-3);
    line-height: 1;
  }

  .sparkline {
    flex-shrink: 0;
    display: block;
  }
</style>
