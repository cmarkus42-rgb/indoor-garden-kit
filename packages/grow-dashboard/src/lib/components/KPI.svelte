<script lang="ts">
  type DeltaTone = 'ok' | 'warn' | 'crit';

  interface Props {
    label: string;
    value: string | number;
    unit: string;
    delta?: number;
    deltaTone?: DeltaTone;
  }

  const { label, value, unit, delta, deltaTone }: Props = $props();

  const arrow = $derived(delta !== undefined ? (delta >= 0 ? '▲' : '▼') : '');
  const deltaAbs = $derived(delta !== undefined ? Math.abs(delta) : 0);
</script>

<div class="kpi">
  <div class="kpi-label">{label}</div>
  <div class="kpi-row">
    <span class="kpi-value">{value}</span>
    <span class="kpi-unit">{unit}</span>
  </div>
  {#if delta !== undefined}
    <div class="kpi-delta" data-tone={deltaTone ?? 'ok'}>
      <span class="kpi-arrow">{arrow}</span>
      <span class="kpi-delta-val">{deltaAbs}</span>
    </div>
  {/if}
</div>

<style>
  .kpi {
    display: flex;
    flex-direction: column;
    gap: 2px;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4) var(--s-5);
  }

  .kpi-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .kpi-row {
    display: flex;
    align-items: baseline;
    gap: 4px;
  }

  .kpi-value {
    font-family: var(--font-mono);
    font-size: var(--t-24);
    color: var(--ink-1);
    line-height: 1.1;
    font-variant-numeric: tabular-nums;
  }

  .kpi-unit {
    font-size: var(--t-12);
    color: var(--ink-3);
    line-height: 1;
  }

  .kpi-delta {
    display: flex;
    align-items: center;
    gap: 2px;
    font-family: var(--font-mono);
    font-size: var(--t-10);
    font-variant-numeric: tabular-nums;
  }

  .kpi-delta[data-tone='ok']   { color: var(--st-ok); }
  .kpi-delta[data-tone='warn'] { color: var(--st-warn); }
  .kpi-delta[data-tone='crit'] { color: var(--st-crit); }

  .kpi-arrow {
    font-size: 8px;
    line-height: 1;
  }
</style>
