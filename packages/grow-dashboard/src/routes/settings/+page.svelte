<script lang="ts">
  import { clearAuth } from '$lib/auth.js';
  import { post, get } from '$lib/api.js';
  import type { StatusResponse, PollingResponse, Device } from '$lib/types.js';
  import StatusDot from '$lib/components/StatusDot.svelte';
  import Chip from '$lib/components/Chip.svelte';
  import { onMount } from 'svelte';

  // -- Theme --
  type Theme = 'botanical' | 'cyberpunk';
  const THEME_KEY = 'grow_theme';
  let theme = $state<Theme>('botanical');

  function setTheme(t: Theme) {
    theme = t;
    if (typeof document !== 'undefined') {
      document.body.dataset.theme = t;
      localStorage.setItem(THEME_KEY, t);
    }
  }

  // -- PIN change --
  let pinCurrent = $state('');
  let pinNew = $state('');
  let pinConfirm = $state('');
  let pinMsg = $state('');
  let pinOk = $state(false);
  let pinSaving = $state(false);

  async function savePin() {
    pinMsg = '';
    if (!pinCurrent || !pinNew || !pinConfirm) {
      pinMsg = 'Fill in all fields.';
      return;
    }
    if (pinNew !== pinConfirm) {
      pinMsg = 'New PINs do not match.';
      pinOk = false;
      return;
    }
    if (!/^\d{4}$/.test(pinNew)) {
      pinMsg = 'PIN must be 4 numeric digits.';
      pinOk = false;
      return;
    }
    pinSaving = true;
    try {
      const res = await post<{ ok: boolean; error?: string }>('/api/auth/change', {
        current: pinCurrent,
        new_pin: pinNew,
      });
      if (res.ok) {
        pinMsg = 'PIN changed successfully.';
        pinOk = true;
        pinCurrent = '';
        pinNew = '';
        pinConfirm = '';
      } else {
        pinMsg = res.error ?? 'Error changing PIN.';
        pinOk = false;
      }
    } catch {
      pinMsg = 'Server unreachable.';
      pinOk = false;
    } finally {
      pinSaving = false;
    }
  }

  // -- Data --
  let devices = $state<Device[]>([]);
  let pollingLoops = $state<Record<string, unknown>>({});

  async function loadData() {
    try {
      const status = await get<StatusResponse>('/api/status');
      devices = status.devices;
    } catch { /* ignore */ }
    try {
      const poll = await get<PollingResponse>('/api/polling');
      pollingLoops = poll.loops;
    } catch { /* ignore */ }
  }

  onMount(() => {
    if (typeof localStorage !== 'undefined') {
      const stored = localStorage.getItem(THEME_KEY);
      theme = stored === 'cyberpunk' ? 'cyberpunk' : 'botanical';
    }
    loadData();
  });

  // -- Helpers --
  function loopStatus(loop: unknown): 'ok' | 'warn' | 'crit' | 'info' {
    if (typeof loop !== 'object' || loop === null) return 'info';
    const l = loop as Record<string, unknown>;
    if (l.error) return 'crit';
    if (l.status === 'running') return 'ok';
    if (l.status === 'paused') return 'warn';
    return 'info';
  }

  function loopStatusLabel(loop: unknown): string {
    if (typeof loop !== 'object' || loop === null) return 'Unknown';
    const l = loop as Record<string, unknown>;
    if (l.error) return 'Error';
    if (l.status === 'running') return 'Active';
    if (l.status === 'paused') return 'Paused';
    return String(l.status ?? 'Unknown');
  }

  function formatLoopKey(key: string): string {
    return key.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
  }

  function deviceStatus(status: string): 'ok' | 'warn' | 'crit' | 'info' {
    if (status === 'online') return 'ok';
    if (status === 'error') return 'crit';
    if (status === 'warning') return 'warn';
    return 'info';
  }
</script>

<div class="settings-page">

  <!-- SECTION: Darstellung -->
  <section class="settings-section">
    <div class="section-h">Darstellung</div>
    <div class="section-body">
      <div class="kv-row">
        <span class="kv-key">Theme</span>
        <div class="theme-switch">
          <button
            class="theme-btn"
            class:theme-active={theme === 'botanical'}
            onclick={() => setTheme('botanical')}
          >
            <span class="theme-dot botanical-dot"></span>
            Botanical
          </button>
          <button
            class="theme-btn"
            class:theme-active={theme === 'cyberpunk'}
            onclick={() => setTheme('cyberpunk')}
          >
            <span class="theme-dot cyberpunk-dot"></span>
            Cyberpunk
          </button>
        </div>
      </div>
    </div>
  </section>

  <!-- SECTION: Sicherheit -->
  <section class="settings-section">
    <div class="section-h">Sicherheit</div>
    <div class="section-body">
      <div class="kv-row">
        <span class="kv-key">Session</span>
        <button class="btn ghost" onclick={() => clearAuth()}>Abmelden</button>
      </div>
      <div class="pin-form">
        <div class="pin-fields">
          <label class="pin-field">
            <span class="pin-label">Aktueller PIN</span>
            <input
              class="pin-input"
              type="password"
              inputmode="numeric"
              maxlength={4}
              bind:value={pinCurrent}
              placeholder="••••"
            />
          </label>
          <label class="pin-field">
            <span class="pin-label">Neuer PIN</span>
            <input
              class="pin-input"
              type="password"
              inputmode="numeric"
              maxlength={4}
              bind:value={pinNew}
              placeholder="••••"
            />
          </label>
          <label class="pin-field">
            <span class="pin-label">Confirm</span>
            <input
              class="pin-input"
              type="password"
              inputmode="numeric"
              maxlength={4}
              bind:value={pinConfirm}
              placeholder="••••"
            />
          </label>
        </div>
        <div class="pin-action">
          <button class="btn primary" onclick={savePin} disabled={pinSaving}>
            {pinSaving ? 'Saving…' : 'Save'}
          </button>
          {#if pinMsg}
            <span class="pin-msg" class:ok={pinOk} class:err={!pinOk}>{pinMsg}</span>
          {/if}
        </div>
      </div>
    </div>
  </section>

  <!-- SECTION: System -->
  <section class="settings-section">
    <div class="section-h">System</div>
    <div class="section-body">
      {#if Object.keys(pollingLoops).length === 0}
        <span class="muted mono small">No polling data</span>
      {:else}
        <div class="loop-list">
          {#each Object.entries(pollingLoops) as [key, loop]}
            {@const st = loopStatus(loop)}
            {@const ldata = typeof loop === 'object' && loop !== null ? (loop as Record<string, unknown>) : {}}
            <div class="loop-row">
              <div class="loop-name-col">
                <StatusDot variant={st} live={st === 'ok'} />
                <span class="loop-name mono">{formatLoopKey(key)}</span>
              </div>
              <div class="loop-meta">
                <Chip variant={st}>{loopStatusLabel(loop)}</Chip>
                {#if ldata.last_run}
                  <span class="kv-pair">
                    <span class="kv-key-s">Last run</span>
                    <span class="kv-val-s mono">{String(ldata.last_run)}</span>
                  </span>
                {/if}
                {#if ldata.error}
                  <span class="loop-error mono">{String(ldata.error)}</span>
                {/if}
              </div>
            </div>
          {/each}
        </div>
      {/if}
    </div>
  </section>

  <!-- SECTION: Devices -->
  <section class="settings-section">
    <div class="section-h">Devices</div>
    {#if devices.length === 0}
      <div class="section-body">
        <span class="muted mono small">No devices</span>
      </div>
    {:else}
      <div class="device-list">
        {#each devices as d}
          {@const st = deviceStatus(d.status)}
          <div class="device-row">
            <div class="device-left">
              <StatusDot variant={st} live={st === 'ok'} />
              <div class="device-info">
                <span class="device-name">{d.name}</span>
                <span class="device-type mono muted">{d.device_type}</span>
              </div>
            </div>
            <div class="device-right">
              <Chip>{d.zone}</Chip>
              <Chip variant={st}>{d.status}</Chip>
              <span class="device-ts mono muted">{d.last_seen}</span>
            </div>
          </div>
        {/each}
      </div>
    {/if}
  </section>

</div>

<style>
  .settings-page {
    display: flex;
    flex-direction: column;
    gap: var(--s-5);
    max-width: 860px;
  }

  /* Section structure */
  .settings-section {
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    overflow: hidden;
    background: var(--bg-1);
  }

  .section-body {
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
  }

  /* KV row */
  .kv-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-4);
  }

  .kv-key {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-3);
    flex-shrink: 0;
  }

  /* Theme switch */
  .theme-switch {
    display: flex;
    gap: var(--s-2);
  }

  .theme-btn {
    display: inline-flex;
    align-items: center;
    gap: var(--s-2);
    padding: 6px 14px;
    background: var(--bg-2);
    border: 1px solid var(--line-strong);
    border-radius: var(--r-1);
    color: var(--ink-3);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    cursor: pointer;
    transition: background 0.12s, border-color 0.12s, color 0.12s;
  }

  .theme-btn:hover {
    background: var(--bg-3);
    color: var(--ink-1);
  }

  .theme-btn.theme-active {
    border: 2px solid var(--accent);
    color: var(--accent);
    background: var(--accent-soft);
  }

  .theme-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }
  .botanical-dot { background: oklch(82% 0.14 145); }
  .cyberpunk-dot { background: oklch(72% 0.28 330); }

  /* PIN form */
  .pin-form {
    border-top: 1px solid var(--line);
    padding-top: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
  }

  .pin-fields {
    display: flex;
    gap: var(--s-4);
    flex-wrap: wrap;
  }

  .pin-field {
    display: flex;
    flex-direction: column;
    gap: var(--s-1);
    flex: 1;
    min-width: 120px;
  }

  .pin-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-4);
  }

  .pin-input {
    font-family: var(--font-mono) !important;
    letter-spacing: 0.3em;
    background: transparent;
    border: none;
    border-bottom: 2px solid var(--line);
    border-radius: 0;
    padding: var(--s-2) var(--s-1);
    color: var(--ink-1);
    font-size: var(--t-14);
    outline: none;
    transition: border-color 0.15s;
    width: 100%;
  }

  .pin-input:focus {
    border-bottom-color: var(--accent);
  }

  .pin-input::placeholder {
    color: var(--ink-4);
    letter-spacing: 0.1em;
  }

  .pin-action {
    display: flex;
    align-items: center;
    gap: var(--s-4);
  }

  .pin-msg {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }
  .pin-msg.ok  { color: var(--st-ok); }
  .pin-msg.err { color: var(--st-crit); }

  /* Loop list */
  .loop-list {
    display: flex;
    flex-direction: column;
    gap: 0;
  }

  .loop-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-4);
    padding: var(--s-2) 0;
    border-bottom: 1px solid var(--line);
    flex-wrap: wrap;
  }
  .loop-row:last-child { border-bottom: none; }

  .loop-name-col {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    min-width: 160px;
  }

  .loop-name {
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: var(--ink-2);
  }

  .loop-meta {
    display: flex;
    align-items: center;
    gap: var(--s-4);
    flex-wrap: wrap;
  }

  .kv-pair {
    display: flex;
    gap: var(--s-2);
    align-items: baseline;
  }
  .kv-key-s {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-4);
  }
  .kv-val-s {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-2);
  }

  .loop-error {
    font-size: var(--t-10);
    color: var(--st-crit);
    max-width: 280px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Device list */
  .device-list {
    display: flex;
    flex-direction: column;
  }

  .device-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-4);
    padding: var(--s-3) var(--s-4);
    border-bottom: 1px solid var(--line);
    transition: background 0.1s;
    flex-wrap: wrap;
  }
  .device-row:last-child { border-bottom: none; }
  .device-row:hover { background: var(--bg-2); }

  .device-left {
    display: flex;
    align-items: center;
    gap: var(--s-3);
  }

  .device-info {
    display: flex;
    flex-direction: column;
    gap: 2px;
  }

  .device-name {
    font-size: var(--t-12);
    color: var(--ink-1);
    font-family: var(--font-sans);
  }

  .device-type {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }

  .device-right {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    flex-wrap: wrap;
  }

  .device-ts {
    font-family: var(--font-mono);
    font-size: var(--t-10);
  }

  /* Utilities */
  .mono { font-family: var(--font-mono); }
  .muted { color: var(--ink-4); }
  .small { font-size: var(--t-10); letter-spacing: 0.08em; text-transform: uppercase; }
</style>
