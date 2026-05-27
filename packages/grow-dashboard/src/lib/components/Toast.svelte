<script lang="ts">
  type Variant = 'ok' | 'info' | 'crit';

  interface Props {
    variant: Variant;
    title: string;
    sub?: string;
    timeout?: number;
  }

  const { variant, title, sub, timeout = 4000 }: Props = $props();

  let visible = $state(true);

  $effect(() => {
    const id = setTimeout(() => {
      visible = false;
    }, timeout);
    return () => clearTimeout(id);
  });
</script>

{#if visible}
  <div class="toast" data-variant={variant} role="status" aria-live="polite">
    <div class="toast-body">
      <div class="toast-text">
        <span class="toast-title">{title}</span>
        {#if sub}
          <span class="toast-sub">{sub}</span>
        {/if}
      </div>
      <button
        class="toast-close"
        aria-label="Dismiss"
        onclick={() => { visible = false; }}
      >✕</button>
    </div>
  </div>
{/if}

<style>
  .toast {
    position: fixed;
    bottom: var(--s-5);
    right: var(--s-5);
    max-width: 380px;
    min-width: 240px;
    z-index: 9999;
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-left: 3px solid transparent;
    border-radius: var(--r-2);
    box-shadow: 0 4px 24px rgba(0, 0, 0, 0.4);
    animation: toast-in 0.22s cubic-bezier(0.34, 1.56, 0.64, 1) both;
  }

  .toast[data-variant='ok']   { border-left-color: var(--st-ok); }
  .toast[data-variant='info'] { border-left-color: var(--st-info); }
  .toast[data-variant='crit'] { border-left-color: var(--st-crit); }

  .toast-body {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: var(--s-3);
    padding: var(--s-3) var(--s-4);
  }

  .toast-text {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
  }

  .toast-title {
    font-size: var(--t-12);
    color: var(--ink-1);
    font-family: var(--font-sans);
    font-weight: 500;
    line-height: 1.3;
  }

  .toast[data-variant='ok']   .toast-title { color: var(--st-ok); }
  .toast[data-variant='info'] .toast-title { color: var(--st-info); }
  .toast[data-variant='crit'] .toast-title { color: var(--st-crit); }

  .toast-sub {
    font-size: var(--t-11);
    color: var(--ink-3);
    line-height: 1.4;
  }

  .toast-close {
    flex-shrink: 0;
    background: none;
    border: none;
    padding: 0;
    cursor: pointer;
    color: var(--ink-4);
    font-size: var(--t-10);
    line-height: 1;
    transition: color 0.15s;
  }

  .toast-close:hover {
    color: var(--ink-2);
  }

  @keyframes toast-in {
    from {
      opacity: 0;
      transform: translateX(12px) translateY(4px);
    }
    to {
      opacity: 1;
      transform: translateX(0) translateY(0);
    }
  }
</style>
