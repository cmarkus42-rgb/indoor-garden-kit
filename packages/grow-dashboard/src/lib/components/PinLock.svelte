<script lang="ts">
  import { verifyPin } from '$lib/auth.js';

  const PIN_LENGTH = 4;

  let digits = $state<string[]>([]);
  let error = $state('');
  let shaking = $state(false);

  function press(n: string) {
    if (digits.length >= PIN_LENGTH) return;
    error = '';
    digits = [...digits, n];

    if (digits.length === PIN_LENGTH) {
      submit();
    }
  }

  function backspace() {
    if (digits.length === 0) return;
    digits = digits.slice(0, -1);
    error = '';
  }

  async function submit() {
    const pin = digits.join('');
    const ok = await verifyPin(pin);
    if (!ok) {
      error = 'Falscher PIN';
      shaking = true;
      setTimeout(() => {
        shaking = false;
        digits = [];
      }, 600);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key >= '0' && e.key <= '9') {
      press(e.key);
    } else if (e.key === 'Backspace') {
      backspace();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="lock-screen">
  <div class="lock">
    <div class="brand-mark">▒</div>
    <h1>Grow · Tent 01</h1>
    <div class="sub">// 4-stelliger PIN</div>
    <div class="pin-dots" class:error={!!error} class:shake={shaking}>
      {#each Array(PIN_LENGTH) as _, i}
        <span class="d" class:on={i < digits.length}></span>
      {/each}
    </div>
    <div class="numpad">
      {#each ['1','2','3','4','5','6','7','8','9'] as n}
        <button onclick={() => press(n)}>{n}</button>
      {/each}
      <button class="ghost">&middot;</button>
      <button onclick={() => press('0')}>0</button>
      <button class="ghost" onclick={backspace}>&larr;</button>
    </div>
    <div class="err" class:show={!!error}>{error || '\u00a0'}</div>
  </div>
</div>

<style>
  .lock-screen {
    position: fixed;
    inset: 0;
    z-index: 1000;
    display: grid;
    place-items: center;
    background: var(--bg-0);
  }

  .lock {
    width: 320px;
    padding: var(--s-8) var(--s-6) var(--s-6);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    text-align: center;
  }

  .brand-mark {
    width: 32px;
    height: 32px;
    border: 1px solid var(--accent);
    color: var(--accent);
    display: grid;
    place-items: center;
    font: 500 14px var(--font-data);
    margin: 0 auto var(--s-4);
    box-shadow: var(--glow);
  }

  h1 {
    font: 500 var(--t-13) var(--font-data);
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--ink-2);
    margin: 0 0 var(--s-1);
  }

  .sub {
    font: 400 var(--t-10) var(--font-data);
    color: var(--ink-4);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: var(--s-6);
  }

  .pin-dots {
    display: flex;
    justify-content: center;
    gap: var(--s-3);
    margin-bottom: var(--s-6);
  }

  .d {
    width: 12px;
    height: 12px;
    border: 1.5px solid var(--ink-3);
    border-radius: 50%;
    transition: background 0.12s, border-color 0.12s;
  }
  .d.on {
    background: var(--accent);
    border-color: var(--accent);
    box-shadow: 0 0 8px var(--accent);
  }

  .pin-dots.error .d { border-color: var(--st-crit); }
  .pin-dots.error .d.on {
    background: var(--st-crit);
    border-color: var(--st-crit);
    box-shadow: 0 0 10px var(--st-crit);
  }

  .numpad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s-2);
  }

  .numpad button {
    aspect-ratio: 1;
    background: var(--bg-2);
    border: 1px solid var(--line);
    color: var(--ink-1);
    font: 500 var(--t-20) var(--font-data);
    border-radius: var(--r-2);
    cursor: pointer;
    transition: background 0.1s, border-color 0.1s;
  }
  .numpad button:hover {
    background: var(--bg-3);
    border-color: var(--accent-line);
  }

  .numpad button.ghost {
    background: transparent;
    border-color: transparent;
    color: var(--ink-3);
    font-size: var(--t-11);
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }
  .numpad button.ghost:hover { color: var(--ink-1); }

  .err {
    margin-top: var(--s-4);
    font: 400 var(--t-10) var(--font-data);
    color: var(--st-crit);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0;
    transition: opacity 0.2s;
    min-height: 1.5em;
  }
  .err.show { opacity: 1; }

  .shake {
    animation: shake 0.4s ease-in-out;
  }

  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20% { transform: translateX(-8px); }
    40% { transform: translateX(8px); }
    60% { transform: translateX(-6px); }
    80% { transform: translateX(6px); }
  }
</style>
