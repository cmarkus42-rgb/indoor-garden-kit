<script lang="ts">
  import { get } from '$lib/api.js';
  import type { AlertsResponse, Alert } from '$lib/types.js';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import Chip from '$lib/components/Chip.svelte';
  import { onMount } from 'svelte';

  let alerts = $state<Alert[]>([]);
  let tierFilter = $state<string>('all');
  let sourceFilter = $state('');

  async function load() {
    const res = await get<AlertsResponse>('/api/alerts');
    alerts = res.alerts;
  }

  onMount(() => { load(); });

  const TIER_OPTIONS = [
    { value: 'all',      label: 'All',      variant: null },
    { value: 'info',     label: 'Info',     variant: 'info' },
    { value: 'warning',  label: 'Warning',  variant: 'warn' },
    { value: 'critical', label: 'Critical', variant: 'crit' },
  ] as const;

  const tierToVariant = (tier: Alert['tier']) =>
    tier === 'info' ? 'info' : tier === 'warning' ? 'warn' : 'crit';

  const filtered = $derived(
    alerts.filter(a => {
      if (tierFilter !== 'all' && a.tier !== tierFilter) return false;
      if (sourceFilter && !a.source.toLowerCase().includes(sourceFilter.toLowerCase())) return false;
      return true;
    })
  );
</script>

<div class="log-page">
  <div class="page-header">
    <div class="section-h">Ereignisprotokoll</div>
    <span class="count mono">{filtered.length}<span class="muted">/{alerts.length}</span></span>
  </div>

  <div class="filter-bar">
    <div class="tier-chips">
      {#each TIER_OPTIONS as opt}
        <button
          class="tier-btn"
          class:active={tierFilter === opt.value}
          data-variant={opt.variant ?? ''}
          onclick={() => { tierFilter = opt.value; }}
        >
          {#if opt.variant}
            <StatusDot variant={opt.variant} />
          {:else}
            <span class="dot-placeholder"></span>
          {/if}
          <span>{opt.label}</span>
        </button>
      {/each}
    </div>

    <div class="source-input-wrap">
      <span class="source-icon mono">//</span>
      <input
        class="source-input"
        type="text"
        bind:value={sourceFilter}
        placeholder="Filter by source…"
      />
      {#if sourceFilter}
        <button class="clear-btn" onclick={() => { sourceFilter = ''; }}>×</button>
      {/if}
    </div>
  </div>

  {#if filtered.length === 0}
    <div class="empty">
      <span class="mono muted">— no entries —</span>
    </div>
  {:else}
    <div class="table-wrap">
      <table class="alert-table">
        <thead>
          <tr>
            <th class="col-tier"></th>
            <th class="col-ts">Timestamp</th>
            <th class="col-src">Source</th>
            <th class="col-msg">Message</th>
            <th class="col-res">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each filtered as a, i}
            <tr class="alert-row" class:resolved={!!a.resolved_at} class:even={i % 2 === 0}>
              <td class="col-tier">
                <StatusDot variant={tierToVariant(a.tier)} live={!a.resolved_at && a.tier === 'critical'} />
              </td>
              <td class="col-ts mono">{a.timestamp}</td>
              <td class="col-src">
                <Chip>{a.source}</Chip>
              </td>
              <td class="col-msg">{a.message}</td>
              <td class="col-res">
                {#if a.resolved_at}
                  <Chip variant="ok">Resolved</Chip>
                {:else}
                  <Chip variant="crit">Open</Chip>
                {/if}
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}
</div>

<style>
  .log-page {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: var(--s-3) var(--s-4);
    border-bottom: 1px solid var(--line);
    background: var(--bg-1);
    border-radius: var(--r-2) var(--r-2) 0 0;
    border: 1px solid var(--line);
    border-bottom: none;
  }

  .count {
    font-size: var(--t-11);
    color: var(--ink-1);
    letter-spacing: 0.06em;
  }

  /* Filter bar */
  .filter-bar {
    display: flex;
    align-items: center;
    gap: var(--s-4);
    padding: var(--s-3) var(--s-4);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-top: 1px solid var(--line-strong);
    border-bottom: none;
    flex-wrap: wrap;
  }

  .tier-chips {
    display: flex;
    gap: var(--s-2);
  }

  .tier-btn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: var(--r-pill);
    border: 1px solid var(--line-strong);
    background: var(--bg-2);
    color: var(--ink-3);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s, color 0.12s;
  }

  .tier-btn:hover {
    background: var(--bg-3);
    color: var(--ink-1);
  }

  .tier-btn.active {
    border-color: var(--accent-line);
    color: var(--ink-1);
    background: var(--accent-soft);
  }

  .tier-btn.active[data-variant='info'] {
    border-color: oklch(72% 0.15 220 / 0.5);
    background: var(--st-info-soft);
    color: var(--st-info);
  }
  .tier-btn.active[data-variant='warn'] {
    border-color: oklch(78% 0.16 75 / 0.5);
    background: var(--st-warn-soft);
    color: var(--st-warn);
  }
  .tier-btn.active[data-variant='crit'] {
    border-color: oklch(68% 0.22 25 / 0.5);
    background: var(--st-crit-soft);
    color: var(--st-crit);
  }

  .dot-placeholder {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    border: 1px solid var(--ink-4);
    flex-shrink: 0;
  }

  .source-input-wrap {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    background: var(--bg-2);
    border: 1px solid var(--line);
    border-radius: var(--r-1);
    padding: 4px var(--s-2);
    transition: border-color 0.12s;
    flex: 1;
    max-width: 280px;
  }

  .source-input-wrap:focus-within {
    border-color: var(--accent-line);
  }

  .source-icon {
    font-size: var(--t-10);
    color: var(--ink-4);
    letter-spacing: -0.05em;
    user-select: none;
    flex-shrink: 0;
  }

  .source-input {
    background: transparent;
    border: none;
    outline: none;
    color: var(--ink-1);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    padding: 0;
    width: 100%;
    min-width: 0;
  }

  .source-input::placeholder {
    color: var(--ink-4);
  }

  .clear-btn {
    background: transparent;
    border: none;
    color: var(--ink-4);
    font-size: var(--t-13);
    cursor: pointer;
    padding: 0 2px;
    line-height: 1;
    flex-shrink: 0;
  }
  .clear-btn:hover { color: var(--ink-1); }

  /* Table */
  .table-wrap {
    border: 1px solid var(--line);
    border-radius: 0 0 var(--r-2) var(--r-2);
    overflow: hidden;
  }

  .alert-table {
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: var(--t-11);
  }

  .alert-table thead tr {
    background: var(--bg-1);
    border-bottom: 1px solid var(--line-strong);
  }

  .alert-table th {
    padding: var(--s-2) var(--s-3);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: var(--ink-4);
    font-weight: 500;
    white-space: nowrap;
  }

  .alert-row td {
    padding: var(--s-2) var(--s-3);
    border-bottom: 1px solid var(--line);
    vertical-align: middle;
    color: var(--ink-2);
    transition: opacity 0.15s;
  }

  .alert-row.even td { background: var(--bg-0); }
  .alert-row:not(.even) td { background: var(--bg-1); }
  .alert-row:hover td { background: var(--bg-2); }

  .alert-row.resolved {
    opacity: 0.5;
  }
  .alert-row.resolved:hover {
    opacity: 0.75;
  }

  .col-tier {
    width: 28px;
    text-align: center;
  }

  .col-ts {
    white-space: nowrap;
    color: var(--ink-3) !important;
    font-size: var(--t-10) !important;
    letter-spacing: 0.04em;
  }

  .col-src {
    white-space: nowrap;
  }

  .col-msg {
    width: 100%;
  }

  .col-res {
    white-space: nowrap;
  }

  .empty {
    padding: var(--s-10) var(--s-4);
    text-align: center;
    border: 1px solid var(--line);
    border-top: none;
    border-radius: 0 0 var(--r-2) var(--r-2);
    background: var(--bg-1);
  }

  .mono {
    font-family: var(--font-mono);
  }
</style>
