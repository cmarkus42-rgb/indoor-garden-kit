<script lang="ts">
  interface Props {
    value: number | string;
    unit: string;
    label: string;
    sub?: string;
    error?: string;
    dirty?: boolean;
    focused?: boolean;
    onStep?: (delta: number) => void;
  }

  let {
    value,
    unit,
    label,
    sub,
    error,
    dirty = false,
    focused = false,
    onStep,
  }: Props = $props();
</script>

<div
  class="card"
  class:card--error={!!error}
  class:card--focused={focused}
  class:card--dirty={dirty}
>
  <div class="card-body">
    {#if onStep}
      <button class="step step--minus" onclick={() => onStep(-1)} aria-label="Decrease">
        <svg width="16" height="16" viewBox="0 0 16 16"><line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    {/if}

    <div class="content">
      <div class="value-row">
        <span class="value" class:value--dirty={dirty}>{value}</span>
        <span class="unit">{unit}</span>
      </div>
      <div class="label-row">
        {#if dirty}
          <span class="dirty-dot"></span>
        {/if}
        <span class="label">{label}</span>
      </div>
      {#if sub}
        <div class="sub">{sub}</div>
      {/if}
    </div>

    {#if onStep}
      <button class="step step--plus" onclick={() => onStep(1)} aria-label="Increase">
        <svg width="16" height="16" viewBox="0 0 16 16"><line x1="4" y1="8" x2="12" y2="8" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/><line x1="8" y1="4" x2="8" y2="12" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/></svg>
      </button>
    {/if}
  </div>

  {#if error}
    <div class="error-msg">{error}</div>
  {/if}
</div>

<style>
  .card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-4);
    transition: border-color 0.15s, box-shadow 0.15s;
  }

  .card--focused {
    border-color: var(--accent-line);
    box-shadow: 0 0 0 1px var(--accent-line);
  }

  .card--error {
    border-color: var(--st-crit);
  }

  .card-body {
    display: flex;
    align-items: center;
    gap: var(--s-2);
  }

  .content {
    flex: 1;
    min-width: 0;
  }

  .value-row {
    display: flex;
    align-items: baseline;
    gap: var(--s-1);
  }

  .value {
    font: 600 var(--t-32) var(--font-mono);
    color: var(--ink-1);
    line-height: 1;
    letter-spacing: -0.02em;
  }

  .value--dirty {
    color: var(--st-recipe);
  }

  .unit {
    font: 400 var(--t-12) var(--font-mono);
    color: var(--ink-3);
  }

  .label-row {
    display: flex;
    align-items: center;
    gap: var(--s-1);
    margin-top: var(--s-1);
  }

  .label {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .dirty-dot {
    width: 6px;
    height: 6px;
    border-radius: 50%;
    background: var(--st-recipe);
    flex-shrink: 0;
    animation: pulse 1.5s ease-in-out infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; transform: scale(1); }
    50% { opacity: 0.4; transform: scale(0.7); }
  }

  .sub {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    margin-top: 2px;
  }

  .error-msg {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--st-crit);
    margin-top: var(--s-2);
    letter-spacing: 0.04em;
  }

  .step {
    display: grid;
    place-items: center;
    width: 32px;
    height: 32px;
    flex-shrink: 0;
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    color: var(--ink-3);
    cursor: pointer;
    transition: background 0.1s, border-color 0.1s, color 0.1s;
  }

  .step:hover {
    background: var(--bg-3);
    border-color: var(--accent-line);
    color: var(--ink-1);
  }

  .step:active {
    background: var(--accent-soft);
  }
</style>
