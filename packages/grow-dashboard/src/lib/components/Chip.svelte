<script lang="ts">
  import type { Snippet } from 'svelte';

  type Variant = 'ok' | 'info' | 'warn' | 'crit' | 'recipe' | 'light';

  interface Props {
    variant?: Variant;
    children: Snippet;
  }

  const { variant, children }: Props = $props();
</script>

<span class="chip" class:has-variant={!!variant} data-variant={variant ?? ''}>
  {@render children()}
</span>

<style>
  .chip {
    display: inline-flex;
    align-items: center;
    padding: 2px 8px;
    border-radius: var(--r-pill);
    font-family: var(--font-mono);
    font-size: var(--t-10);
    text-transform: uppercase;
    letter-spacing: 0.12em;
    line-height: 1.6;
    white-space: nowrap;
    background: var(--bg-2);
    color: var(--ink-2);
  }

  .chip[data-variant='ok']     { background: var(--st-ok-soft);     color: var(--st-ok); }
  .chip[data-variant='info']   { background: var(--st-info-soft);   color: var(--st-info); }
  .chip[data-variant='warn']   { background: var(--st-warn-soft);   color: var(--st-warn); }
  .chip[data-variant='crit']   { background: var(--st-crit-soft);   color: var(--st-crit); }
  .chip[data-variant='recipe'] { background: var(--st-recipe-soft); color: var(--st-recipe); }
  .chip[data-variant='light']  { background: var(--st-light-soft);  color: var(--st-light); }
</style>
