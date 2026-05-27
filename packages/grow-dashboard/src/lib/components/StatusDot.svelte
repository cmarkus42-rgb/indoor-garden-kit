<script lang="ts">
  type Variant = 'ok' | 'info' | 'warn' | 'crit' | 'recipe' | 'light';

  interface Props {
    variant: Variant;
    live?: boolean;
  }

  const { variant, live = false }: Props = $props();
</script>

<span
  class="status-dot"
  class:live
  data-variant={variant}
  aria-label={variant}
></span>

<style>
  .status-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    flex-shrink: 0;
  }

  .status-dot[data-variant='ok']     { background: var(--st-ok); }
  .status-dot[data-variant='info']   { background: var(--st-info); }
  .status-dot[data-variant='warn']   { background: var(--st-warn); }
  .status-dot[data-variant='crit']   { background: var(--st-crit); }
  .status-dot[data-variant='recipe'] { background: var(--st-recipe); }
  .status-dot[data-variant='light']  { background: var(--st-light); }

  .status-dot.live[data-variant='ok']     { animation: pulse-ok 2s ease-in-out infinite; }
  .status-dot.live[data-variant='info']   { animation: pulse-info 2s ease-in-out infinite; }
  .status-dot.live[data-variant='warn']   { animation: pulse-warn 2s ease-in-out infinite; }
  .status-dot.live[data-variant='crit']   { animation: pulse-crit 2s ease-in-out infinite; }
  .status-dot.live[data-variant='recipe'] { animation: pulse-recipe 2s ease-in-out infinite; }
  .status-dot.live[data-variant='light']  { animation: pulse-light 2s ease-in-out infinite; }

  @keyframes pulse-ok {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-ok-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-ok-soft); }
  }
  @keyframes pulse-info {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-info-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-info-soft); }
  }
  @keyframes pulse-warn {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-warn-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-warn-soft); }
  }
  @keyframes pulse-crit {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-crit-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-crit-soft); }
  }
  @keyframes pulse-recipe {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-recipe-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-recipe-soft); }
  }
  @keyframes pulse-light {
    0%, 100% { box-shadow: 0 0 0 0 var(--st-light-soft); }
    50%       { box-shadow: 0 0 0 5px var(--st-light-soft); }
  }
</style>
