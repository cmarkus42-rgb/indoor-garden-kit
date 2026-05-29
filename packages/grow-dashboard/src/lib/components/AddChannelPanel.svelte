<script lang="ts">
  import type { ChannelRule } from '$lib/types.js';

  interface ChannelTemplate {
    label: string;
    name: string;
    rule: ChannelRule;
  }

  interface Props {
    onAdd: (name: string, rule: ChannelRule) => void;
    existingNames: string[];
  }

  let { onAdd, existingNames }: Props = $props();

  const templates: ChannelTemplate[] = [
    {
      label: 'Pre-Night',
      name: 'far_red',
      rule: { rule: 'before_on', offset_min: 30, duration_min: 30 },
    },
    {
      label: 'Infrared',
      name: 'infrared',
      rule: { rule: 'after_off', offset_min: 0, duration_min: 15 },
    },
    {
      label: 'UV',
      name: 'uva',
      rule: { rule: 'window', windows: [{ start: '12:00', duration_min: 30 }] },
    },
    {
      label: 'Custom',
      name: '',
      rule: { rule: 'before_on', offset_min: 0, duration_min: 15 },
    },
  ];

  const RULE_LABELS: Record<string, string> = {
    before_on: 'before_on',
    after_off: 'after_off',
    window: 'window',
  };

  function pickName(base: string): string {
    if (!base) {
      const custom = prompt('Channel name:');
      return custom?.trim() ?? '';
    }
    if (!existingNames.includes(base)) return base;
    let i = 2;
    while (existingNames.includes(`${base}_${i}`)) i++;
    return `${base}_${i}`;
  }

  function select(tpl: ChannelTemplate) {
    const name = pickName(tpl.name);
    if (!name) return;
    onAdd(name, structuredClone(tpl.rule));
  }
</script>

<div class="add-panel">
  <div class="panel-label">Add Channel</div>
  <div class="grid">
    {#each templates as tpl}
      <button class="template-card" onclick={() => select(tpl)}>
        <span class="tpl-name">{tpl.label}</span>
        <span class="tpl-rule">{RULE_LABELS[tpl.rule.rule]}</span>
        {#if tpl.rule.rule !== 'window'}
          <span class="tpl-detail">{tpl.rule.duration_min} min</span>
        {:else if tpl.rule.windows?.length}
          <span class="tpl-detail">{tpl.rule.windows[0].duration_min} min @ {tpl.rule.windows[0].start}</span>
        {/if}
      </button>
    {/each}
  </div>
</div>

<style>
  .add-panel {
    border: 2px dashed var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
  }

  .panel-label {
    font: 500 var(--t-10) var(--font-mono);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: var(--s-3);
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-3);
  }

  .template-card {
    display: flex;
    flex-direction: column;
    align-items: flex-start;
    gap: var(--s-1);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-3) var(--s-4);
    cursor: pointer;
    transition: border-color 0.15s, background 0.15s;
  }

  .template-card:hover {
    border-color: var(--accent-line);
    background: var(--bg-3);
  }

  .template-card:active {
    background: var(--accent-soft);
  }

  .tpl-name {
    font: 600 var(--t-12) var(--font-mono);
    color: var(--ink-1);
  }

  .tpl-rule {
    font: 400 var(--t-9) var(--font-mono);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .tpl-detail {
    font: 400 var(--t-10) var(--font-mono);
    color: var(--ink-3);
  }
</style>
