<script lang="ts">
  import { page } from '$app/stores';
  import { verified } from '$lib/auth.js';
  import { sseStart, sseStop, sseConnected } from '$lib/sse.js';
  import { onMount, onDestroy } from 'svelte';
  import '../app.css';

  const { children } = $props();

  const THEME_KEY = 'grow_theme';
  type Theme = 'botanical' | 'cyberpunk';

  let theme = $state<Theme>('botanical');

  function loadTheme(): Theme {
    if (typeof localStorage === 'undefined') return 'botanical';
    const stored = localStorage.getItem(THEME_KEY);
    return stored === 'cyberpunk' ? 'cyberpunk' : 'botanical';
  }

  function setTheme(t: Theme) {
    theme = t;
    document.body.dataset.theme = t;
    localStorage.setItem(THEME_KEY, t);
  }

  const links = [
    { href: '/', label: 'Overview' },
    { href: '/climate', label: 'Climate' },
    { href: '/soil', label: 'Soil' },
    { href: '/light', label: 'Light' },
    { href: '/recipes', label: 'Recipes' },
    { href: '/energy', label: 'Energy' },
    { href: '/log', label: 'Log' },
    { href: '/investigate', label: 'Investigate' },
    { href: '/settings', label: 'Settings' }
  ];

  onMount(() => {
    theme = loadTheme();
    document.body.dataset.theme = theme;
    sseStart();
  });

  onDestroy(() => {
    sseStop();
  });
</script>

<svelte:head>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin="anonymous" />
  <link href="https://fonts.googleapis.com/css2?family=Inter+Tight:wght@400;500;600&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet" />
</svelte:head>

{#if !$verified}
  <PinLock />
{:else}
  <header class="appbar">
    <div class="brand">
      <span class="mark">▒</span>
      <span>Grow · Tent 01</span>
    </div>
    <nav>
      {#each links as link}
        <a href={link.href} class:active={$page.url.pathname === link.href}>{link.label}</a>
      {/each}
    </nav>
    <div class="right">
      <span class="chip" class:ok={$sseConnected} class:crit={!$sseConnected}>
        <span class="dot" class:ok={$sseConnected} class:live={$sseConnected} class:crit={!$sseConnected}></span>
        {$sseConnected ? 'SSE' : 'Offline'}
      </span>
      <button
        class="theme-btn"
        onclick={() => setTheme(theme === 'botanical' ? 'cyberpunk' : 'botanical')}
      >
        {theme === 'botanical' ? 'Cyberpunk' : 'Botanical'}
      </button>
    </div>
  </header>
  <main class="page-content">
    {@render children()}
  </main>
{/if}

<script lang="ts" module>
  import PinLock from '$lib/components/PinLock.svelte';
</script>

<style>
  .appbar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 48px;
    padding: 0 var(--s-5);
    border-bottom: 1px solid var(--line);
    background: var(--bg-1);
    position: sticky;
    top: 0;
    z-index: 50;
  }

  .brand {
    display: flex;
    align-items: center;
    gap: var(--s-3);
    font-family: var(--font-data);
    font-size: var(--t-12);
    letter-spacing: 0.18em;
    text-transform: uppercase;
  }

  .mark {
    width: 18px;
    height: 18px;
    border: 1px solid var(--accent);
    display: grid;
    place-items: center;
    color: var(--accent);
    font-size: 10px;
    box-shadow: var(--glow);
  }

  nav {
    display: flex;
    gap: 2px;
    font-family: var(--font-data);
    font-size: var(--t-11);
  }

  nav a {
    padding: 6px 10px;
    color: var(--ink-3);
    text-decoration: none;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid transparent;
  }
  nav a.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  nav a:hover { color: var(--ink-1); }

  .right {
    display: flex;
    gap: var(--s-3);
    align-items: center;
    font-family: var(--font-data);
    font-size: var(--t-11);
    color: var(--ink-3);
  }

  .theme-btn {
    background: var(--bg-2);
    border: 1px solid var(--line);
    color: var(--ink-3);
    font-family: var(--font-data);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    padding: 4px 10px;
    border-radius: var(--r-1);
    cursor: pointer;
    transition: background 0.12s, color 0.12s;
  }
  .theme-btn:hover { background: var(--bg-3); color: var(--ink-1); }

  .page-content {
    padding: var(--s-5);
    max-width: 1400px;
    margin: 0 auto;
  }
</style>
