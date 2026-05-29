<script lang="ts" module>
  import type uPlot from 'uplot';

  export const LOG_STEPS = [
    { seconds: 3600,        label: 'Last hour' },
    { seconds: 10800,       label: 'Last 3 hours' },
    { seconds: 21600,       label: 'Last 6 hours' },
    { seconds: 43200,       label: 'Last 12 hours' },
    { seconds: 86400,       label: 'Last 24 hours' },
    { seconds: 259200,      label: 'Last 3 days' },
    { seconds: 604800,      label: 'Last 7 days' },
    { seconds: 1209600,     label: 'Last 14 days' },
    { seconds: 2592000,     label: 'Last 30 days' },
    { seconds: 15552000,    label: 'Last 6 months' },
    { seconds: 31536000,    label: 'Last year' },
    { seconds: Infinity,    label: 'All data' },
  ] as const;

  export function filterByRange(rangeStep: number | string, aligned: uPlot.AlignedData): uPlot.AlignedData {
    const step = LOG_STEPS[Number(rangeStep)];
    if (step.seconds === Infinity || !aligned[0]?.length) return aligned;
    const xs = aligned[0] as number[];
    const cutoff = Math.round(Date.now() / 1000) - step.seconds;
    const startIdx = xs.findIndex(t => t >= cutoff);
    if (startIdx < 0) return aligned;
    return aligned.map(arr => (arr as number[]).slice(startIdx)) as uPlot.AlignedData;
  }
</script>

<script lang="ts">
  interface Props {
    value?: number;
  }

  let { value = $bindable(4) }: Props = $props();

  let label = $derived(LOG_STEPS[value].label);
</script>

<div class="time-slider-wrap">
  <input
    type="range"
    class="time-slider"
    min="0"
    max={LOG_STEPS.length - 1}
    bind:value={value}
  />
  <span class="time-slider-label">{label}</span>
</div>

<style>
  .time-slider-wrap {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: 0 var(--s-2);
  }

  .time-slider {
    flex: 1;
    appearance: none;
    height: 4px;
    border-radius: 2px;
    background: var(--line);
    outline: none;
    cursor: pointer;
  }

  .time-slider::-webkit-slider-thumb {
    appearance: none;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: oklch(72% 0.16 145);
    border: 2px solid var(--bg-0);
    cursor: pointer;
    transition: transform 0.1s;
  }

  .time-slider::-webkit-slider-thumb:hover {
    transform: scale(1.2);
  }

  .time-slider::-moz-range-thumb {
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: oklch(72% 0.16 145);
    border: 2px solid var(--bg-0);
    cursor: pointer;
  }

  .time-slider-label {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-3);
    white-space: nowrap;
    min-width: 100px;
    text-align: right;
  }
</style>
