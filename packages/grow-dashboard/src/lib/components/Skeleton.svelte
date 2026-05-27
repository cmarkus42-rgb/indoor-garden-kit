<script lang="ts">
  interface Props {
    width?: string;
    height?: string;
  }

  const { width = '100%', height = '16px' }: Props = $props();
</script>

<div class="skeleton" style:width style:height aria-hidden="true"></div>

<style>
  .skeleton {
    border-radius: var(--r-1);
    background: linear-gradient(
      90deg,
      var(--bg-2) 0%,
      var(--bg-3) 50%,
      var(--bg-2) 100%
    );
    background-size: 200% 100%;
    animation: skeleton-sweep 1.4s ease-in-out infinite;
  }

  @keyframes skeleton-sweep {
    0%   { background-position: 200% 0; }
    100% { background-position: -200% 0; }
  }
</style>
