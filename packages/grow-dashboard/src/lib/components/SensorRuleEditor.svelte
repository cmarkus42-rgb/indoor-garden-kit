<script lang="ts">
  import type { ProportionalRule, SensorRuleType, ResponseType, StepBreakpoint, DeviceGroup } from '$lib/types.js';

  interface Props {
    rule: ProportionalRule;
    groups: DeviceGroup[];
    onSave: (rule: ProportionalRule) => void;
    onCancel: () => void;
  }

  let { rule, groups, onSave, onCancel }: Props = $props();

  let form = $state<ProportionalRule>({ ...rule, steps: rule.steps.map(s => ({ ...s })) });

  const SENSOR_TYPES: { value: SensorRuleType; label: string }[] = [
    { value: 'vpd', label: 'VPD' },
    { value: 'temperature', label: 'Temperature' },
    { value: 'humidity', label: 'Humidity' },
    { value: 'soil_moisture', label: 'Soil Moisture' },
  ];

  const SENSOR_UNITS: Record<SensorRuleType, string> = {
    vpd: 'kPa',
    temperature: '°C',
    humidity: '%',
    soil_moisture: '%',
  };

  function addStep() {
    const last = form.steps[form.steps.length - 1];
    form.steps = [...form.steps, { threshold: last ? last.threshold + 1 : form.target_value, output: 5 }];
  }

  function removeStep(idx: number) {
    form.steps = form.steps.filter((_, i) => i !== idx);
  }

  function updateStep(idx: number, field: 'threshold' | 'output', value: number) {
    form.steps = form.steps.map((s, i) => i === idx ? { ...s, [field]: value } : s);
  }

  function handleSubmit() {
    onSave(form);
  }

  // SVG Response curve visualization
  let curveUnit = $derived(SENSOR_UNITS[form.sensor_type]);

  const SVG_W = 280;
  const SVG_H = 80;
  const SVG_PAD = { l: 28, r: 8, t: 6, b: 16 };

  function svgX(v: number, xMin: number, xRange: number) {
    return SVG_PAD.l + ((v - xMin) / xRange) * (SVG_W - SVG_PAD.l - SVG_PAD.r);
  }
  function svgY(o: number) {
    return SVG_H - SVG_PAD.b - (o / 10) * (SVG_H - SVG_PAD.t - SVG_PAD.b);
  }

  let curveData = $derived.by(() => {
    const maxO = form.max_output;

    if (form.response_type === 'stepped' && form.steps.length > 0) {
      const sorted = [...form.steps].sort((a, b) => a.threshold - b.threshold);
      const pad = (sorted[sorted.length - 1].threshold - sorted[0].threshold) * 0.15 || 1;
      const xMin = sorted[0].threshold - pad;
      const xRange = (sorted[sorted.length - 1].threshold - sorted[0].threshold) + 2 * pad || 1;

      const pts: string[] = [];
      for (let i = 0; i < sorted.length; i++) {
        const x = svgX(sorted[i].threshold, xMin, xRange);
        const y = svgY(sorted[i].output);
        if (i > 0) pts.push(`${x},${svgY(sorted[i - 1].output)}`);
        pts.push(`${x},${y}`);
      }
      return { polyline: pts.join(' '), xMin, xRange, sorted, dbX1: 0, dbX2: 0, axisLabels: sorted.map(s => ({ x: svgX(s.threshold, xMin, xRange), label: String(s.threshold) })) };
    }

    // Linear
    const target = form.target_value;
    const db = Math.max(form.deadband, 0.01);
    const margin = db * 2.5;
    const xMin = target - db - margin;
    const xMax = target + db + margin;
    const xRange = xMax - xMin || 1;

    const rampOut = form.invert_response ? form.min_output : maxO;
    const rampIn = form.invert_response ? maxO : form.min_output;

    const pts = [
      `${svgX(xMin, xMin, xRange)},${svgY(rampOut)}`,
      `${svgX(target - db, xMin, xRange)},${svgY(rampIn)}`,
      `${svgX(target - db, xMin, xRange)},${svgY(0)}`,
      `${svgX(target + db, xMin, xRange)},${svgY(0)}`,
      `${svgX(target + db, xMin, xRange)},${svgY(rampIn)}`,
      `${svgX(xMax, xMin, xRange)},${svgY(rampOut)}`,
    ];

    const dbX1 = svgX(target - db, xMin, xRange);
    const dbX2 = svgX(target + db, xMin, xRange);

    return {
      polyline: pts.join(' '), xMin, xRange, sorted: [] as StepBreakpoint[],
      dbX1, dbX2,
      axisLabels: [
        { x: svgX(target - db, xMin, xRange), label: (target - db).toFixed(1) },
        { x: svgX(target, xMin, xRange), label: String(target) },
        { x: svgX(target + db, xMin, xRange), label: (target + db).toFixed(1) },
      ]
    };
  });
</script>

<div class="editor">
  <div class="editor-header">
    <span class="editor-title">{form.id ? 'Edit Rule' : 'New Rule'}</span>
    <label class="toggle-row">
      <span class="field-label">Enabled</span>
      <button
        class="toggle-btn"
        class:toggle-on={form.enabled}
        onclick={() => { form.enabled = !form.enabled; }}
      >
        <span class="toggle-track"><span class="toggle-thumb"></span></span>
      </button>
    </label>
  </div>

  <div class="form-grid">
    <!-- Sensor Type -->
    <div class="field">
      <label class="field-label">Sensor Type</label>
      <select bind:value={form.sensor_type}>
        {#each SENSOR_TYPES as st}
          <option value={st.value}>{st.label}</option>
        {/each}
      </select>
    </div>

    <!-- Target Value -->
    <div class="field">
      <label class="field-label">Target Value ({curveUnit})</label>
      <input type="number" step="0.1" bind:value={form.target_value} />
    </div>

    <!-- Deadband -->
    <div class="field">
      <label class="field-label">Deadband ({curveUnit})</label>
      <input type="number" step="0.1" min="0" bind:value={form.deadband} />
    </div>

    <!-- Response Type -->
    <div class="field">
      <label class="field-label">Response Type</label>
      <div class="response-toggle">
        <button
          class="resp-btn"
          class:resp-active={form.response_type === 'linear'}
          onclick={() => { form.response_type = 'linear'; }}
        >Linear</button>
        <button
          class="resp-btn"
          class:resp-active={form.response_type === 'stepped'}
          onclick={() => { form.response_type = 'stepped'; }}
        >Stepped</button>
      </div>
    </div>

    <!-- Min/Max Output -->
    <div class="field">
      <label class="field-label">Min Output (0-10)</label>
      <input type="number" min="0" max="10" step="1" bind:value={form.min_output} />
    </div>

    <div class="field">
      <label class="field-label">Max Output (0-10)</label>
      <input type="number" min="0" max="10" step="1" bind:value={form.max_output} />
    </div>

    <!-- Target Group -->
    <div class="field">
      <label class="field-label">Target Group</label>
      <select bind:value={form.target_group_id}>
        <option value="">— none —</option>
        {#each groups as g}
          <option value={g.id}>{g.name}</option>
        {/each}
      </select>
    </div>

    <!-- Target Port -->
    <div class="field">
      <label class="field-label">Target Port</label>
      <input type="number" min="0" max="8" step="1" bind:value={form.target_port} />
    </div>
  </div>

  <!-- Invert Response -->
  <label class="toggle-row invert-row">
    <span class="field-label">Invert Response</span>
    <button
      class="toggle-btn"
      class:toggle-on={form.invert_response}
      onclick={() => { form.invert_response = !form.invert_response; }}
    >
      <span class="toggle-track"><span class="toggle-thumb"></span></span>
    </button>
  </label>

  <!-- Steps Editor (only for stepped) -->
  {#if form.response_type === 'stepped'}
    <div class="steps-section">
      <div class="steps-header">
        <span class="field-label">Breakpoints</span>
        <button class="btn-add-step" onclick={addStep}>+ Add</button>
      </div>
      {#if form.steps.length === 0}
        <p class="empty-hint">No breakpoints defined</p>
      {/if}
      {#each form.steps as step, idx}
        <div class="step-row">
          <div class="step-field">
            <span class="step-label">Threshold</span>
            <input
              type="number"
              step="0.1"
              value={step.threshold}
              oninput={(e) => updateStep(idx, 'threshold', parseFloat((e.target as HTMLInputElement).value) || 0)}
            />
          </div>
          <div class="step-field">
            <span class="step-label">Output</span>
            <input
              type="number"
              min="0"
              max="10"
              step="1"
              value={step.output}
              oninput={(e) => updateStep(idx, 'output', parseFloat((e.target as HTMLInputElement).value) || 0)}
            />
          </div>
          <button class="btn-remove-step" onclick={() => removeStep(idx)}>✕</button>
        </div>
      {/each}
    </div>
  {/if}

  <!-- SVG Response Curve -->
  <div class="curve-section">
    <span class="field-label">Response</span>
    <div class="curve-wrap">
      <svg viewBox="0 0 {SVG_W} {SVG_H}" class="curve-svg">
        <!-- Axes -->
        <line x1={SVG_PAD.l} y1={SVG_H - SVG_PAD.b} x2={SVG_W - SVG_PAD.r} y2={SVG_H - SVG_PAD.b} class="axis" />
        <line x1={SVG_PAD.l} y1={SVG_PAD.t} x2={SVG_PAD.l} y2={SVG_H - SVG_PAD.b} class="axis" />
        <!-- Y-axis labels -->
        <text x={SVG_PAD.l - 3} y={svgY(0) + 1} class="ax-val" text-anchor="end">0</text>
        <text x={SVG_PAD.l - 3} y={svgY(form.max_output) + 1} class="ax-val" text-anchor="end">{form.max_output}</text>
        <!-- Deadband zone -->
        {#if form.response_type === 'linear' && curveData.dbX2 > curveData.dbX1}
          <rect x={curveData.dbX1} y={SVG_PAD.t} width={curveData.dbX2 - curveData.dbX1} height={SVG_H - SVG_PAD.t - SVG_PAD.b} class="deadband-zone" />
        {/if}
        <!-- Curve -->
        <polyline points={curveData.polyline} class="curve-line" />
        <!-- X-axis value labels -->
        {#each curveData.axisLabels as al}
          <text x={al.x} y={SVG_H - 3} class="ax-val" text-anchor="middle">{al.label}</text>
        {/each}
      </svg>
    </div>
  </div>

  <!-- Actions -->
  <div class="editor-actions">
    <button class="btn-save" onclick={handleSubmit}>Save</button>
    <button class="btn-cancel" onclick={onCancel}>Cancel</button>
  </div>
</div>

<style>
  .editor {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    padding: var(--s-3);
    display: flex;
    flex-direction: column;
    gap: var(--s-2);
  }

  .editor-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .editor-title {
    font-family: var(--font-mono);
    font-size: var(--t-12);
    color: var(--ink-1);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .field-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: var(--s-2);
  }

  .field {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .field select,
  .field input {
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    padding: var(--s-1) var(--s-2);
    outline: none;
  }

  .field select:focus,
  .field input:focus {
    border-color: var(--accent-line);
  }

  /* Toggle button */
  .toggle-row {
    display: flex;
    align-items: center;
    gap: var(--s-3);
  }

  .invert-row {
    padding: 0;
  }

  .toggle-btn {
    background: none;
    border: none;
    cursor: pointer;
    padding: 0;
  }

  .toggle-track {
    display: flex;
    align-items: center;
    width: 32px;
    height: 18px;
    border-radius: var(--r-pill);
    background: var(--line);
    padding: 2px;
    transition: background 0.15s;
  }

  .toggle-on .toggle-track {
    background: var(--accent, oklch(78% 0.16 145));
  }

  .toggle-thumb {
    display: block;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--bg-0);
    transition: transform 0.15s;
  }

  .toggle-on .toggle-thumb {
    transform: translateX(14px);
  }

  /* Response type toggle */
  .response-toggle {
    display: flex;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    overflow: hidden;
  }

  .resp-btn {
    flex: 1;
    background: var(--bg-0);
    border: none;
    color: var(--ink-3);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    padding: var(--s-2) var(--s-3);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }

  .resp-btn.resp-active {
    background: var(--accent-soft, oklch(78% 0.16 145 / 0.14));
    color: var(--accent, oklch(78% 0.16 145));
  }

  /* Steps section */
  .steps-section {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
  }

  .steps-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  .btn-add-step {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-3);
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 2px var(--s-3);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
    transition: color 0.1s, border-color 0.1s;
  }

  .btn-add-step:hover {
    color: var(--ink-1);
    border-color: var(--ink-3);
  }

  .empty-hint {
    font-size: var(--t-11);
    color: var(--ink-4);
    margin: 0;
    text-align: center;
    padding: var(--s-2) 0;
  }

  .step-row {
    display: flex;
    align-items: flex-end;
    gap: var(--s-3);
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: var(--s-2) var(--s-3);
  }

  .step-field {
    display: flex;
    flex-direction: column;
    gap: 2px;
    flex: 1;
  }

  .step-label {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .step-field input {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-1);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    padding: var(--s-1) var(--s-2);
    width: 100%;
  }

  .btn-remove-step {
    background: none;
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    color: var(--ink-4);
    font-size: var(--t-11);
    padding: var(--s-1) var(--s-2);
    cursor: pointer;
    transition: color 0.1s, border-color 0.1s;
    flex-shrink: 0;
  }

  .btn-remove-step:hover {
    color: var(--st-crit);
    border-color: var(--st-crit);
  }

  /* SVG Curve */
  .curve-section {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .curve-wrap {
    background: var(--bg-0);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: var(--s-1) var(--s-2);
  }

  .curve-svg {
    width: 100%;
    max-height: 80px;
  }

  .curve-svg .axis {
    stroke: var(--line-strong, var(--line));
    stroke-width: 0.5;
  }

  .curve-svg .deadband-zone {
    fill: var(--accent, oklch(78% 0.16 145));
    opacity: 0.08;
  }

  .curve-svg .curve-line {
    fill: none;
    stroke: var(--accent, oklch(78% 0.16 145));
    stroke-width: 1.5;
    stroke-linejoin: round;
  }

  .curve-svg .ax-val {
    font-family: var(--font-mono);
    font-size: 5px;
    fill: var(--ink-4);
  }

  /* Actions */
  .editor-actions {
    display: flex;
    gap: var(--s-3);
  }

  .btn-save {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    background: var(--accent, oklch(78% 0.16 145));
    color: var(--bg-0);
    border: none;
    border-radius: var(--r-1);
    padding: var(--s-2) var(--s-5);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .btn-cancel {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    background: none;
    color: var(--ink-3);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: var(--s-2) var(--s-5);
    cursor: pointer;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  @media (max-width: 768px) {
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
