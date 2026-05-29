<script lang="ts">
  import { get, post } from '$lib/api.js';
  import { onMount, onDestroy } from 'svelte';
  import StatusDot from '$lib/components/StatusDot.svelte';

  interface CameraInfo {
    name: string;
    host: string;
    rtsp_url_safe: string;
  }

  interface StreamUrls {
    webrtc: string;
    mse: string;
    mjpeg: string;
    snapshot: string;
  }

  let cameras = $state<CameraInfo[]>([]);
  let streams = $state<Record<string, StreamUrls>>({});
  let activeCam = $state<string>('');
  let loading = $state(true);
  let snapshotSaving = $state(false);
  let snapshotMsg = $state('');
  let streamMode = $state<'mjpeg' | 'snapshot'>('mjpeg');
  let snapshotTimer: ReturnType<typeof setInterval> | null = null;
  let snapshotUrl = $state('');
  let snapshotTs = $state(0);

  async function load() {
    try {
      const [camRes, streamRes] = await Promise.all([
        get<{ cameras: CameraInfo[] }>('/api/camera/list'),
        get<{ streams: Record<string, StreamUrls> }>('/api/camera/stream-urls'),
      ]);
      cameras = camRes.cameras;
      streams = streamRes.streams;
      if (cameras.length && !activeCam) {
        activeCam = cameras[0].name;
      }
    } catch {
      // Camera system not configured
    }
    loading = false;
  }

  function refreshSnapshot() {
    if (!activeCam || !streams[activeCam]) return;
    snapshotTs = Date.now();
    snapshotUrl = `${streams[activeCam].snapshot}?t=${snapshotTs}`;
  }

  function startSnapshotRefresh() {
    refreshSnapshot();
    snapshotTimer = setInterval(refreshSnapshot, 2000);
  }

  function stopSnapshotRefresh() {
    if (snapshotTimer) {
      clearInterval(snapshotTimer);
      snapshotTimer = null;
    }
  }

  $effect(() => {
    const cam = activeCam;
    if (cam && streams[cam]) {
      stopSnapshotRefresh();
      if (streamMode === 'snapshot') {
        startSnapshotRefresh();
      }
    }
  });

  onMount(() => {
    load();
  });

  onDestroy(() => {
    stopSnapshotRefresh();
  });

  async function saveSnapshot() {
    if (!activeCam) return;
    snapshotSaving = true;
    snapshotMsg = '';
    try {
      const res = await post<{ status: string; path: string }>(
        `/api/camera/${activeCam}/snapshot/save`, {}
      );
      snapshotMsg = `Saved: ${res.path.split('/').slice(-2).join('/')}`;
    } catch (e) {
      snapshotMsg = 'Save failed';
    }
    snapshotSaving = false;
    setTimeout(() => { snapshotMsg = ''; }, 4000);
  }

  async function ptzStep(angle: number) {
    if (!activeCam) return;
    await post(`/api/camera/${activeCam}/ptz/step`, { angle });
  }

  async function ptzMove(x: number, y: number) {
    if (!activeCam) return;
    await post(`/api/camera/${activeCam}/ptz/move`, { x, y });
  }

  function getMjpegUrl(cam: string): string {
    if (!streams[cam]) return '';
    return streams[cam].mjpeg;
  }
</script>

<div class="page">
  <header class="page-header">
    <h1>Cameras</h1>
    {#if cameras.length > 1}
      <div class="cam-switcher">
        {#each cameras as cam}
          <button
            class="cam-btn"
            class:active={activeCam === cam.name}
            onclick={() => { activeCam = cam.name; }}
          >
            <StatusDot variant="ok" />
            {cam.name}
          </button>
        {/each}
      </div>
    {/if}
  </header>

  {#if loading}
    <div class="loading">
      <div class="loading-bar"></div>
      <span class="loading-text">Loading cameras…</span>
    </div>
  {:else if cameras.length === 0}
    <div class="empty">No cameras configured. Add camera.toml to enable.</div>
  {:else}
    <!-- Stream viewer -->
    <div class="viewer-card">
      <div class="stream-container">
        {#if streamMode === 'mjpeg' && getMjpegUrl(activeCam)}
          <img
            class="stream-img"
            src={getMjpegUrl(activeCam)}
            alt="Live stream {activeCam}"
          />
        {:else if streamMode === 'snapshot' && snapshotUrl}
          <img
            class="stream-img"
            src={snapshotUrl}
            alt="Snapshot {activeCam}"
          />
        {:else}
          <div class="no-stream">Stream unavailable</div>
        {/if}
      </div>

      <!-- Controls bar -->
      <div class="controls-bar">
        <div class="mode-switcher">
          <button
            class="mode-btn"
            class:active={streamMode === 'mjpeg'}
            onclick={() => { streamMode = 'mjpeg'; stopSnapshotRefresh(); }}
          >MJPEG</button>
          <button
            class="mode-btn"
            class:active={streamMode === 'snapshot'}
            onclick={() => { streamMode = 'snapshot'; startSnapshotRefresh(); }}
          >Snapshot</button>
        </div>

        <button
          class="action-btn"
          onclick={saveSnapshot}
          disabled={snapshotSaving}
        >
          {snapshotSaving ? 'Saving…' : 'Save Snapshot'}
        </button>

        {#if snapshotMsg}
          <span class="snapshot-msg">{snapshotMsg}</span>
        {/if}
      </div>
    </div>

    <!-- PTZ Controls -->
    <div class="ptz-card">
      <header class="section-header">
        <span class="section-label">PTZ Control</span>
      </header>
      <div class="ptz-grid">
        <div class="ptz-spacer"></div>
        <button class="ptz-btn" onclick={() => ptzStep(0)} title="Up">▲</button>
        <div class="ptz-spacer"></div>
        <button class="ptz-btn" onclick={() => ptzStep(270)} title="Left">◄</button>
        <button class="ptz-btn ptz-center" onclick={() => ptzMove(0, 0)} title="Home">●</button>
        <button class="ptz-btn" onclick={() => ptzStep(90)} title="Right">►</button>
        <div class="ptz-spacer"></div>
        <button class="ptz-btn" onclick={() => ptzStep(180)} title="Down">▼</button>
        <div class="ptz-spacer"></div>
      </div>
    </div>
  {/if}
</div>

<style>
  .page {
    display: flex;
    flex-direction: column;
    gap: var(--s-4);
    padding: var(--s-4);
    background: var(--bg-0);
    min-height: 100%;
  }

  .page-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-4);
  }

  h1 {
    font-family: var(--font-mono);
    font-size: var(--t-14);
    color: var(--ink-1);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .cam-switcher {
    display: flex;
    gap: var(--s-2);
  }

  .cam-btn {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    padding: var(--s-2) var(--s-3);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-3);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-pill);
    cursor: pointer;
    transition: all 0.15s;
  }

  .cam-btn.active {
    color: var(--accent);
    border-color: var(--accent);
  }

  .cam-btn:hover { color: var(--ink-1); }

  /* Viewer */
  .viewer-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    overflow: hidden;
  }

  .stream-container {
    position: relative;
    width: 100%;
    aspect-ratio: 16 / 9;
    background: #000;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .stream-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .no-stream {
    color: var(--ink-4);
    font-family: var(--font-mono);
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .controls-bar {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-3) var(--s-4);
    border-top: 1px solid var(--line);
  }

  .mode-switcher {
    display: flex;
    gap: 1px;
    border-radius: var(--r-1);
    overflow: hidden;
    border: 1px solid var(--line);
  }

  .mode-btn {
    padding: var(--s-1) var(--s-3);
    font-family: var(--font-mono);
    font-size: var(--t-9);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--ink-3);
    background: var(--bg-0);
    border: none;
    cursor: pointer;
    transition: all 0.15s;
  }

  .mode-btn.active {
    background: var(--accent);
    color: var(--bg-0);
  }

  .action-btn {
    margin-left: auto;
    padding: var(--s-2) var(--s-4);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    background: var(--bg-0);
    color: var(--ink-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    cursor: pointer;
    transition: all 0.15s;
  }

  .action-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .action-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .snapshot-msg {
    font-family: var(--font-mono);
    font-size: var(--t-9);
    color: var(--st-ok);
  }

  /* PTZ */
  .ptz-card {
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-3);
    padding: var(--s-4);
    display: flex;
    flex-direction: column;
    gap: var(--s-3);
    max-width: 280px;
  }

  .section-header {
    display: flex;
    align-items: baseline;
  }

  .section-label {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-3);
    text-transform: uppercase;
    letter-spacing: 0.12em;
  }

  .ptz-grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s-2);
    justify-items: center;
  }

  .ptz-btn {
    width: 44px;
    height: 44px;
    display: grid;
    place-items: center;
    font-size: 16px;
    background: var(--bg-0);
    color: var(--ink-2);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    cursor: pointer;
    transition: all 0.15s;
  }

  .ptz-btn:hover {
    border-color: var(--accent);
    color: var(--accent);
  }

  .ptz-btn:active {
    background: var(--accent);
    color: var(--bg-0);
  }

  .ptz-center {
    border-radius: 50%;
    background: var(--line);
    font-size: 10px;
  }

  .ptz-spacer {
    width: 44px;
    height: 44px;
  }

  /* Loading / empty */
  .loading {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: var(--s-3);
    padding: var(--s-10) 0;
  }

  .loading-bar {
    width: 120px;
    height: 2px;
    background: var(--line);
    border-radius: 1px;
    overflow: hidden;
    position: relative;
  }

  .loading-bar::after {
    content: '';
    position: absolute;
    inset-block: 0;
    left: -40%;
    width: 40%;
    background: var(--accent);
    border-radius: 1px;
    animation: slide 1.2s ease-in-out infinite;
  }

  @keyframes slide { to { left: 100%; } }

  .loading-text {
    font-family: var(--font-mono);
    font-size: var(--t-10);
    color: var(--ink-4);
    text-transform: uppercase;
    letter-spacing: 0.1em;
  }

  .empty {
    font-family: var(--font-mono);
    font-size: var(--t-11);
    color: var(--ink-4);
    text-align: center;
    padding: var(--s-10) 0;
  }
</style>
