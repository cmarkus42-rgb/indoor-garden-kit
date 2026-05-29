<script lang="ts">
  import { getSensorRules, createSensorRule, updateSensorRule, deleteSensorRule, getGroups } from '$lib/api.js';
  import type { ProportionalRule, DeviceGroup, SensorRuleType } from '$lib/types.js';
  import SensorRuleEditor from '$lib/components/SensorRuleEditor.svelte';
  import { onMount } from 'svelte';

  let rules = $state<ProportionalRule[]>([]);
  let groups = $state<DeviceGroup[]>([]);
  let loading = $state(true);
  let editingRule = $state<ProportionalRule | null>(null);

  const SENSOR_LABELS: Record<SensorRuleType, string> = {
    vpd: 'VPD',
    temperature: 'Temperature',
    humidity: 'Humidity',
    soil_moisture: 'Soil Moisture',
  };

  function emptyRule(): ProportionalRule {
    return {
      enabled: true,
      sensor_type: 'vpd',
      target_value: 1.2,
      deadband: 0.2,
      response_type: 'linear',
      min_output: 0,
      max_output: 10,
      invert_response: false,
      target_group_id: '',
      target_port: 1,
      steps: [],
    };
  }

  function startNew() {
    editingRule = emptyRule();
  }

  function startEdit(rule: ProportionalRule) {
    editingRule = { ...rule, steps: rule.steps.map(s => ({ ...s })) };
  }

  async function handleSave(rule: ProportionalRule) {
    try {
      if (rule.id) {
        const { id, ...body } = rule;
        const updated = await updateSensorRule(id, body);
        rules = rules.map(r => r.id === id ? updated : r);
      } else {
        const created = await createSensorRule(rule);
        rules = [...rules, created];
      }
      editingRule = null;
    } catch { /* keep editor open on error */ }
  }

  function handleCancel() {
    editingRule = null;
  }

  async function handleDelete(id: string) {
    try {
      await deleteSensorRule(id);
      rules = rules.filter(r => r.id !== id);
    } catch { /* ignore */ }
  }

  async function handleToggle(rule: ProportionalRule) {
    if (!rule.id) return;
    const { id, ...body } = rule;
    try {
      const updated = await updateSensorRule(id, { ...body, enabled: !rule.enabled });
      rules = rules.map(r => r.id === id ? updated : r);
    } catch { /* ignore */ }
  }

  function groupName(groupId: string): string {
    return groups.find(g => g.id === groupId)?.name ?? '—';
  }

  onMount(async () => {
    try {
      const [rulesRes, groupsRes] = await Promise.all([
        getSensorRules(),
        getGroups(),
      ]);
      rules = rulesRes.rules;
      groups = groupsRes.groups;
    } catch { /* ignore */ }
    loading = false;
  });
</script>

<div class="page">
  <div class="page-header">
    <h1 class="page-title">Sensor Rules</h1>
    {#if !editingRule}
      <button class="btn primary" onclick={startNew}>+ New Rule</button>
    {/if}
  </div>

  {#if editingRule}
    <SensorRuleEditor
      rule={editingRule}
      {groups}
      onSave={handleSave}
      onCancel={handleCancel}
    />
  {:else if loading}
    <div class="loading-state">Loading rules...</div>
  {:else if rules.length === 0}
    <div class="empty-state">
      <p>No sensor rules defined yet.</p>
      <p class="muted">Proportional sensor rules let you automatically control devices based on sensor readings.</p>
    </div>
  {:else}
    <div class="rules-grid">
      {#each rules as rule (rule.id)}
        <div class="rule-card" class:rule-disabled={!rule.enabled}>
          <div class="rule-card-header">
            <span class="rule-sensor-chip">{SENSOR_LABELS[rule.sensor_type]}</span>
            <button
              class="status-toggle"
              class:status-on={rule.enabled}
              onclick={() => handleToggle(rule)}
              aria-label={rule.enabled ? 'Disable rule' : 'Enable rule'}
            >
              <span class="status-track"><span class="status-thumb"></span></span>
            </button>
          </div>

          <div class="rule-card-body">
            <div class="rule-kv">
              <span class="rule-k">Target</span>
              <span class="rule-v">{rule.target_value}</span>
            </div>
            <div class="rule-kv">
              <span class="rule-k">Deadband</span>
              <span class="rule-v">&plusmn;{rule.deadband}</span>
            </div>
            <div class="rule-kv">
              <span class="rule-k">Response</span>
              <span class="rule-v">{rule.response_type}</span>
            </div>
            <div class="rule-kv">
              <span class="rule-k">Output</span>
              <span class="rule-v">{rule.min_output}–{rule.max_output}</span>
            </div>
            <div class="rule-kv">
              <span class="rule-k">Group</span>
              <span class="rule-v">{groupName(rule.target_group_id)}</span>
            </div>
            <div class="rule-kv">
              <span class="rule-k">Port</span>
              <span class="rule-v">{rule.target_port}</span>
            </div>
            {#if rule.invert_response}
              <div class="rule-badge">Inverted</div>
            {/if}
            {#if rule.response_type === 'stepped' && rule.steps.length > 0}
              <div class="rule-steps-hint">{rule.steps.length} breakpoint{rule.steps.length > 1 ? 's' : ''}</div>
            {/if}
          </div>

          <div class="rule-card-actions">
            <button class="btn ghost" onclick={() => startEdit(rule)}>Edit</button>
            <button class="btn-delete" onclick={() => rule.id && handleDelete(rule.id)}>Delete</button>
          </div>
        </div>
      {/each}
    </div>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-5);
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .page-title {
    font-family: var(--font-mono);
    font-size: var(--t-16);
    font-weight: 500;
    color: var(--ink-1);
    letter-spacing: -0.01em;
    margin: 0;
  }

  .loading-state {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-8) 0;
  }

  .empty-state {
    text-align: center;
    padding: var(--s-10) var(--s-4);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
  }

  .empty-state p {
    margin: 0 0 var(--s-2);
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-2);
  }

  /* Rules grid */
  .rules-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: var(--s-4);
  }

  .rule-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    display: flex;
    flex-direction: column;
    transition: border-color 0.15s;
  }

  .rule-card:hover {
    border-color: var(--line-strong, var(--ink-4));
  }

  .rule-card.rule-disabled {
    opacity: 0.5;
  }

  .rule-card-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s-3) var(--s-4);
    border-bottom: 1px solid var(--line);
  }

  .rule-sensor-chip {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--accent, oklch(78% 0.16 145));
    background: var(--accent-soft, oklch(78% 0.16 145 / 0.14));
    border: 1px solid var(--accent-line, oklch(78% 0.16 145 / 0.3));
    border-radius: var(--r-pill);
    padding: 2px 10px;
  }

  /* Status toggle */
  .status-toggle {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .status-track {
    display: flex;
    align-items: center;
    width: 28px;
    height: 16px;
    border-radius: var(--r-pill);
    background: var(--line);
    padding: 2px;
    transition: background 0.15s;
  }

  .status-on .status-track {
    background: var(--st-ok);
  }

  .status-thumb {
    display: block;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: var(--bg-0);
    transition: transform 0.15s;
  }

  .status-on .status-thumb {
    transform: translateX(12px);
  }

  .rule-card-body {
    padding: var(--s-3) var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
    flex: 1;
  }

  .rule-kv {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    font-family: var(--font-mono);
    font-size: var(--t-11);
    padding: 2px 0;
  }

  .rule-k {
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-size: var(--t-10);
  }

  .rule-v {
    color: var(--ink-1);
    font-variant-numeric: tabular-nums;
  }

  .rule-badge {
    display: inline-block;
    align-self: flex-start;
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--st-warn);
    background: var(--st-warn-soft);
    border: 1px solid oklch(78% 0.16 75 / 0.3);
    border-radius: var(--r-pill);
    padding: 1px 8px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-top: var(--s-1);
  }

  .rule-steps-hint {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    margin-top: var(--s-1);
  }

  .rule-card-actions {
    display: flex;
    gap: var(--s-2);
    padding: var(--s-3) var(--s-4);
    border-top: 1px solid var(--line);
  }

  .btn-delete {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: var(--s-1) var(--s-3);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    transition: color 0.1s, border-color 0.1s;
  }

  .btn-delete:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
    background: var(--st-crit-soft);
  }

  @media (max-width: 768px) {
    .rules-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
