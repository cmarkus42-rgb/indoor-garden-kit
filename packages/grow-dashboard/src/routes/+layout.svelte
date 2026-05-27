<script lang="ts">
  import { page } from '$app/stores';
  import { goto } from '$app/navigation';
  import { verified } from '$lib/auth.js';
  import { sseStart, sseStop, sseConnected } from '$lib/sse.js';
  import { onMount, onDestroy } from 'svelte';
  import '../app.css';

  const { children } = $props();

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
    sseStart();
  });

  onDestroy(() => {
    sseStop();
  });

  // Auth guard: redirect to /settings if not verified (except /settings itself)
  $effect(() => {
    const path = $page.url.pathname as string;
    if (!$verified && path !== '/settings') {
      goto('/settings');
    }
  });
</script>

<nav>
  {#each links as link}
    <a href={link.href} class:active={$page.url.pathname === link.href}>{link.label}</a>
  {/each}
  <span class="muted" style="margin-left:auto">
    SSE: {$sseConnected ? 'connected' : 'disconnected'}
  </span>
</nav>

{@render children()}

<style>
  .active { font-weight: bold; text-decoration: underline; }
</style>
