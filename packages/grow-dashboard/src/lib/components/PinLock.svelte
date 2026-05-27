<script lang="ts">
  import { verifyPin } from '$lib/auth.js';

  const PIN_LENGTH = 4;

  let digits = $state<string[]>([]);
  let error = $state('');
  let shaking = $state(false);
  let errorBorder = $state(false);

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
    if (digits.length < PIN_LENGTH) return;
    const pin = digits.join('');
    const ok = await verifyPin(pin);
    if (!ok) {
      error = 'Falscher PIN';
      shaking = true;
      errorBorder = true;
      setTimeout(() => {
        shaking = false;
        digits = [];
      }, 600);
      setTimeout(() => {
        errorBorder = false;
        error = '';
      }, 2500);
    }
  }

  function handleKeydown(e: KeyboardEvent) {
    if (e.key >= '0' && e.key <= '9') {
      press(e.key);
    } else if (e.key === 'Backspace') {
      backspace();
    } else if (e.key === 'Enter') {
      submit();
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="lock-screen">
  <div class="lock">
    <div class="brand-mark">▒</div>
    <h1 class="lock-title">Grow Dashboard</h1>
    <div class="sub">// Tent 01 · PIN erforderlich</div>

    <div class="pin-display" class:error={errorBorder} class:shake={shaking}>
      {#each Array(PIN_LENGTH) as _, i}
        <div class="pin-slot" class:filled={i < digits.length} class:active={i === digits.length}>
          {#if i < digits.length}
            <span class="pin-bullet">●</span>
          {:else}
            <span class="pin-placeholder">_</span>
          {/if}
        </div>
      {/each}
    </div>

    <div class="numpad">
      {#each ['1','2','3','4','5','6','7','8','9'] as n}
        <button onclick={() => press(n)}>{n}</button>
      {/each}
      <button class="ghost">&middot;</button>
      <button onclick={() => press('0')}>0</button>
      <button class="ghost back" onclick={backspace}>⌫</button>
    </div>

    <button class="unlock-btn" onclick={submit} disabled={digits.length < PIN_LENGTH}>
      Entsperren
    </button>

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
    width: 340px;
    padding: var(--s-8) var(--s-6) var(--s-6);
    background: var(--bg-1);
    border: 1px solid var(--line);
    border-radius: var(--r-2);
    text-align: center;
    box-shadow: 0 24px 80px oklch(0% 0 0 / 0.5);
  }

  .brand-mark {
    width: 36px;
    height: 36px;
    border: 1px solid var(--accent);
    color: var(--accent);
    display: grid;
    place-items: center;
    font: 600 15px var(--font-data);
    margin: 0 auto var(--s-4);
    box-shadow: var(--glow);
  }

  .lock-title {
    font-family: var(--font-data);
    font-size: var(--t-24);
    font-weight: 500;
    color: var(--ink-1);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    margin: 0 0 var(--s-1);
  }

  .sub {
    font: 400 var(--t-10) var(--font-data);
    color: var(--ink-4);
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-bottom: var(--s-6);
  }

  /* PIN display — underline style */
  .pin-display {
    display: flex;
    justify-content: center;
    gap: var(--s-3);
    margin-bottom: var(--s-6);
  }

  .pin-slot {
    width: 44px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    font-family: var(--font-mono);
    letter-spacing: 0.3em;
    padding-bottom: var(--s-1);
    border-bottom: 2px solid var(--line);
    transition: border-color 0.15s;
    height: 36px;
  }

  .pin-slot.active {
    border-bottom-color: var(--accent);
  }

  .pin-bullet {
    font-size: var(--t-16);
    color: var(--accent);
    line-height: 1;
  }

  .pin-placeholder {
    font-size: var(--t-14);
    color: var(--ink-4);
    line-height: 1;
    opacity: 0.4;
  }

  .pin-display.error .pin-slot {
    border-bottom-color: var(--st-crit);
  }
  .pin-display.error .pin-bullet {
    color: var(--st-crit);
  }

  /* Numpad */
  .numpad {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: var(--s-2);
    margin-bottom: var(--s-4);
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
  .numpad button:active {
    background: var(--accent-soft);
    border-color: var(--accent-line);
  }

  .numpad button.ghost {
    background: transparent;
    border-color: transparent;
    color: var(--ink-3);
    font-size: var(--t-13);
  }
  .numpad button.ghost:hover { color: var(--ink-1); background: transparent; }

  .numpad button.back {
    font-size: var(--t-14);
  }

  /* Unlock button */
  .unlock-btn {
    width: 100%;
    background: var(--accent);
    border: none;
    border-radius: var(--r-2);
    color: var(--bg-0);
    font: 600 var(--t-12) var(--font-data);
    text-transform: uppercase;
    letter-spacing: 0.14em;
    padding: var(--s-3) var(--s-6);
    cursor: pointer;
    transition: opacity 0.15s, box-shadow 0.15s;
    margin-bottom: 0;
  }

  .unlock-btn:hover:not(:disabled) {
    box-shadow: var(--glow);
    opacity: 0.92;
  }

  .unlock-btn:disabled {
    opacity: 0.28;
    cursor: not-allowed;
  }

  /* Error */
  .err {
    margin-top: var(--s-3);
    font: 400 var(--t-10) var(--font-data);
    color: var(--st-crit);
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0;
    transition: opacity 0.2s;
    min-height: 1.5em;
  }
  .err.show { opacity: 1; }

  /* Shake animation */
  .shake {
    animation: shake 0.4s ease-in-out;
  }

  @keyframes shake {
    0%, 100% { transform: translateX(0); }
    20%       { transform: translateX(-8px); }
    40%       { transform: translateX(8px); }
    60%       { transform: translateX(-6px); }
    80%       { transform: translateX(6px); }
  }
</style>
