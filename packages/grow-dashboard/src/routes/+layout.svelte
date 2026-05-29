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
  let moreOpen = $state(false);

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

  function toggleMore() {
    moreOpen = !moreOpen;
  }

  function closeMore() {
    moreOpen = false;
  }

  const primaryLinks = [
    { href: '/',             label: 'Overview',     icon: '◎' },
    { href: '/devices',      label: 'Devices',      icon: '◧' },
    { href: '/climate',      label: 'Climate',       icon: '◌' },
    { href: '/recipes',      label: 'Recipes',      icon: '◈' },
    { href: '/energy',       label: 'Energy',       icon: '◉' },
  ];

  const moreLinks = [
    { href: '/sensor-rules', label: 'Sensor Rules' },
    { href: '/cameras',      label: 'Cameras'      },
    { href: '/investigate',  label: 'Investigate'   },
    { href: '/log',          label: 'Log'           },
    { href: '/settings',     label: 'Settings'      },
  ];

  const desktopLinks = [
    { href: '/',              label: 'Overview'      },
    { href: '/devices',       label: 'Devices'       },
    { href: '/climate',       label: 'Climate'       },
    { href: '/recipes',       label: 'Recipes'       },
    { href: '/sensor-rules',  label: 'Sensor Rules'  },
    { href: '/energy',        label: 'Energy'        },
    { href: '/investigate',   label: 'Investigate'   },
  ];

  const isMoreActive = $derived(
    moreLinks.some(l => $page.url.pathname === l.href)
  );

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
    <nav class="desktop-nav">
      {#each desktopLinks as link}
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

  <!-- Mobile bottom tab bar -->
  <nav class="mobile-tabs" aria-label="Main navigation">
    {#each primaryLinks as link}
      <a
        href={link.href}
        class="tab-item"
        class:tab-active={$page.url.pathname === link.href}
        onclick={closeMore}
      >
        <span class="tab-icon">{link.icon}</span>
        <span class="tab-label">{link.label}</span>
      </a>
    {/each}

    <button
      class="tab-item tab-more"
      class:tab-active={isMoreActive || moreOpen}
      onclick={toggleMore}
      aria-expanded={moreOpen}
    >
      <span class="tab-icon">≡</span>
      <span class="tab-label">More</span>
    </button>

    {#if moreOpen}
      <!-- svelte-ignore a11y_click_events_have_key_events -->
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="more-backdrop" onclick={closeMore}></div>
      <div class="more-dropdown">
        <div class="more-header mono">More pages</div>
        {#each moreLinks as link}
          <a
            href={link.href}
            class="more-item"
            class:more-active={$page.url.pathname === link.href}
            onclick={closeMore}
          >
            <span class="more-label">{link.label}</span>
            {#if $page.url.pathname === link.href}
              <span class="more-dot"></span>
            {/if}
          </a>
        {/each}
      </div>
    {/if}
  </nav>
{/if}

<script lang="ts" module>
  import PinLock from '$lib/components/PinLock.svelte';
</script>

<style>
  /* ── Desktop appbar ──────────────────────────────────────── */
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

  .desktop-nav {
    display: flex;
    gap: 2px;
    font-family: var(--font-data);
    font-size: var(--t-11);
  }

  .desktop-nav a {
    padding: 6px 10px;
    color: var(--ink-3);
    text-decoration: none;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    border-bottom: 1px solid transparent;
  }
  .desktop-nav a.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
  }
  .desktop-nav a:hover { color: var(--ink-1); }

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

  /* ── Mobile bottom tab bar ───────────────────────────────── */
  .mobile-tabs {
    display: none;
  }

  @media (max-width: 768px) {
    .appbar {
      height: 44px;
      padding: 0 var(--s-3);
    }

    .desktop-nav {
      display: none;
    }

    .right {
      font-size: var(--t-10);
      gap: var(--s-2);
    }

    .theme-btn {
      display: none;
    }

    .page-content {
      padding: var(--s-3) var(--s-3) calc(var(--s-3) + 60px);
    }

    .mobile-tabs {
      display: flex;
      align-items: stretch;
      position: fixed;
      bottom: 0;
      left: 0;
      right: 0;
      z-index: 100;
      background: var(--bg-1);
      border-top: 1px solid var(--line);
      height: 60px;
      padding-bottom: env(safe-area-inset-bottom, 0);
    }

    .tab-item {
      flex: 1;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      gap: 3px;
      color: var(--ink-4);
      text-decoration: none;
      font-family: var(--font-mono);
      font-size: var(--t-9);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      background: transparent;
      border: none;
      cursor: pointer;
      transition: color 0.12s;
      padding: var(--s-1) 0;
    }

    .tab-item.tab-active {
      color: var(--accent);
    }

    .tab-item:hover {
      color: var(--ink-2);
    }

    .tab-item.tab-active:hover {
      color: var(--accent);
    }

    .tab-icon {
      font-size: 18px;
      line-height: 1;
    }

    .tab-label {
      font-size: var(--t-9);
      letter-spacing: 0.06em;
    }

    /* Mehr dropdown */
    .more-backdrop {
      position: fixed;
      inset: 0;
      bottom: 60px;
      z-index: 98;
    }

    .more-dropdown {
      position: fixed;
      bottom: 60px;
      right: 0;
      width: 220px;
      background: var(--bg-1);
      border: 1px solid var(--line-strong);
      border-bottom: none;
      border-radius: var(--r-2) var(--r-2) 0 0;
      z-index: 99;
      overflow: hidden;
      box-shadow: 0 -8px 32px oklch(0% 0 0 / 0.4);
    }

    .more-header {
      padding: var(--s-2) var(--s-4);
      font-size: var(--t-10);
      text-transform: uppercase;
      letter-spacing: 0.14em;
      color: var(--ink-4);
      border-bottom: 1px solid var(--line);
      font-family: var(--font-mono);
    }

    .more-item {
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: var(--s-3) var(--s-4);
      color: var(--ink-2);
      text-decoration: none;
      font-family: var(--font-mono);
      font-size: var(--t-11);
      text-transform: uppercase;
      letter-spacing: 0.1em;
      border-bottom: 1px solid var(--line);
      transition: background 0.1s, color 0.1s;
    }
    .more-item:last-child { border-bottom: none; }
    .more-item:hover { background: var(--bg-2); color: var(--ink-1); }
    .more-item.more-active { color: var(--accent); }

    .more-dot {
      width: 6px;
      height: 6px;
      border-radius: 50%;
      background: var(--accent);
      box-shadow: 0 0 6px var(--accent);
    }
  }
</style>
