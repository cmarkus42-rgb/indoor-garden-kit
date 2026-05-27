<script lang="ts">
  import type { Snippet } from 'svelte';

  type Variant = 'crit' | 'warn' | 'info';

  interface Props {
    variant: Variant;
    title: string;
    sub?: string;
    children?: Snippet;
  }

  const { variant, title, sub, children }: Props = $props();
</script>

<div class="banner" data-variant={variant} role="alert">
  <div class="banner-content">
    <div class="banner-text">
      <span class="banner-title">{title}</span>
      {#if sub}
        <span class="banner-sub">{sub}</span>
      {/if}
    </div>
    {#if children}
      <div class="banner-actions">
        {@render children()}
      </div>
    {/if}
  </div>
</div>

<style>
  .banner {
    width: 100%;
    padding: var(--s-3) var(--s-4);
    border-left: 3px solid transparent;
    border-radius: var(--r-1);
  }

  .banner[data-variant='crit'] {
    border-left-color: var(--st-crit);
    background: var(--st-crit-soft);
  }
  .banner[data-variant='warn'] {
    border-left-color: var(--st-warn);
    background: var(--st-warn-soft);
  }
  .banner[data-variant='info'] {
    border-left-color: var(--st-info);
    background: var(--st-info-soft);
  }

  .banner-content {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--s-4);
  }

  .banner-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .banner-title {
    font-size: var(--t-12);
    color: var(--ink-1);
    font-family: var(--font-sans);
    font-weight: 500;
  }

  .banner[data-variant='crit'] .banner-title { color: var(--st-crit); }
  .banner[data-variant='warn'] .banner-title { color: var(--st-warn); }
  .banner[data-variant='info'] .banner-title { color: var(--st-info); }

  .banner-sub {
    font-size: var(--t-11);
    color: var(--ink-3);
    line-height: 1.4;
  }

  .banner-actions {
    display: flex;
    align-items: center;
    gap: var(--s-2);
    flex-shrink: 0;
  }
</style>
