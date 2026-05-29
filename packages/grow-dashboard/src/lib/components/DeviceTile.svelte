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
    lastSeen?: string;
    periodic?: boolean;
    toggled?: boolean | null;
    onToggle?: () => void;
    onEdit?: () => void;
    groupColor?: string;
    dimmerValue?: number;
    onDimmer?: (pct: number) => void;
  }

  const { label, sub, metric, unit, status, sparklinePoints, lastSeen, periodic, toggled, onToggle, onEdit, groupColor, dimmerValue, onDimmer }: Props = $props();

  function formatTimeAgo(isoDate: string): string {
    const diffMin = Math.floor((Date.now() - new Date(isoDate).getTime()) / 60_000);
    if (diffMin < 1) return 'just now';
    if (diffMin < 60) return `${diffMin} min ago`;
    const diffH = Math.floor(diffMin / 60);
    if (diffH < 24) return `${diffH}h ago`;
    return `${Math.floor(diffH / 24)}d ago`;
  }

  const isStale = $derived(
    lastSeen != null && (Date.now() - new Date(lastSeen).getTime()) > 10 * 60_000
  );

  const timeAgo = $derived(lastSeen != null ? formatTimeAgo(lastSeen) : null);

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

<div class="tile" class:offline={status === 'offline'} class:stale={isStale} class:has-group={!!groupColor} data-status={status} style:border-left-color={groupColor ?? undefined}>
  {#if status === 'offline'}
    <div class="offline-overlay" aria-hidden="true"></div>
  {/if}

  {#if onEdit}
    <button class="edit-btn" onclick={onEdit} title="Rename device">✎</button>
  {/if}

  <div class="tile-header">
    <div class="tile-labels">
      <span class="tile-label">{label}</span>
      {#if sub}
        <span class="tile-sub">{sub}</span>
      {/if}
    </div>
    <StatusDot variant={dotVariant} live={status === 'ok' && !periodic} />
  </div>

  <div class="tile-body">
    <div class="tile-metric-col">
      <div class="tile-metric-row">
        <span class="tile-metric">{metric}</span>
        <span class="tile-unit">{unit}</span>
      </div>
      {#if periodic && timeAgo}
        <span class="tile-timestamp">{timeAgo}</span>
      {/if}
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
    {#if onToggle != null && toggled != null}
      <button
        class="toggle"
        class:on={toggled}
        onclick={onToggle}
        aria-label={toggled ? 'Turn off' : 'Turn on'}
        aria-pressed={toggled}
      >
        <span class="toggle-thumb"></span>
      </button>
    {/if}
  </div>

  {#if onDimmer != null && dimmerValue != null}
    <div class="dimmer-row">
      <input
        type="range"
        class="dimmer-slider"
        min="0"
        max="100"
        value={dimmerValue}
        oninput={(e) => onDimmer(Number(e.currentTarget.value))}
        aria-label="Brightness"
      />
      <span class="dimmer-label">{dimmerValue}%</span>
    </div>
  {/if}
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

  .tile.has-group {
    border-left-width: 3px;
  }

  .edit-btn {
    position: absolute;
    top: var(--s-2);
    right: var(--s-2);
    z-index: 2;
    background: oklch(0% 0 0 / 0.4);
    border: none;
    cursor: pointer;
    color: var(--ink-2);
    font-size: var(--t-11);
    padding: 2px 6px;
    border-radius: var(--r-1);
    line-height: 1;
    opacity: 0.6;
    transition: opacity 0.15s, background 0.15s;
  }

  .edit-btn:hover {
    opacity: 1;
    background: oklch(0% 0 0 / 0.6);
  }

  .tile.offline {
    opacity: 0.7;
  }

  .tile.stale .tile-metric,
  .tile.stale .tile-unit {
    color: var(--ink-4);
    opacity: 0.6;
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

  .tile-metric-col {
    display: flex;
    flex-direction: column;
    gap: 3px;
  }

  .tile-metric-row {
    display: flex;
    align-items: baseline;
    gap: 3px;
  }

  .tile-timestamp {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    line-height: 1;
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

  .toggle {
    flex-shrink: 0;
    position: relative;
    width: 32px;
    height: 18px;
    border-radius: var(--r-pill);
    background: var(--line);
    border: none;
    cursor: pointer;
    padding: 0;
    transition: background 0.15s;
    align-self: flex-end;
  }

  .toggle.on {
    background: var(--accent);
  }

  .toggle-thumb {
    position: absolute;
    top: 2px;
    left: 2px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--bg-0);
    transition: transform 0.15s;
  }

  .toggle.on .toggle-thumb {
    transform: translateX(14px);
  }

  /* ── Dimmer slider ───────────────────────────────────────────────────── */
  .dimmer-row {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding-top: var(--s-1);
  }

  .dimmer-slider {
    flex: 1;
    -webkit-appearance: none;
    appearance: none;
    height: 4px;
    background: var(--line);
    border-radius: var(--r-pill);
    outline: none;
    cursor: pointer;
  }

  .dimmer-slider::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg-0);
    cursor: pointer;
  }

  .dimmer-slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--accent);
    border: 2px solid var(--bg-0);
    cursor: pointer;
  }

  .dimmer-label {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    min-width: 32px;
    text-align: right;
  }
</style>
