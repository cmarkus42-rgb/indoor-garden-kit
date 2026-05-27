<script lang="ts">
  import { get, put } from '$lib/api.js';
  import { sseLatest } from '$lib/sse.js';
  import type {
    SchedulesResponse, LightSchedule,
    DayPlanResponse, QueueResponse, RecipesResponse, RecipeSummary
  } from '$lib/types.js';
  import { onMount } from 'svelte';

  let schedules = $state<LightSchedule[]>([]);
  let dayPlan = $state<DayPlanResponse | null>(null);
  let queue = $state<QueueResponse | null>(null);
  let allRecipes = $state<RecipeSummary[]>([]);

  // Transition dialog
  let showTransition = $state(false);
  let transitionTarget = $state('');
  let transitionDays = $state(7);

  async function load() {
    const [schedRes, queueRes, recipesRes] = await Promise.all([
      get<SchedulesResponse>('/api/schedules'),
      get<QueueResponse>('/api/queue'),
      get<RecipesResponse>('/api/recipes'),
    ]);
    schedules = schedRes.schedules;
    queue = queueRes;
    allRecipes = recipesRes.recipes;

    try {
      dayPlan = await get<DayPlanResponse>('/api/schedule/today');
    } catch {
      dayPlan = null;
    }
  }

  onMount(() => { load(); });

  $effect(() => {
    const evt = $sseLatest;
    if (evt?.type === 'schedule_pushed') {
      load();
    }
  });

  function minuteToPercent(m: number): number {
    return (m / 1440) * 100;
  }

  function minuteToHHMM(m: number): string {
    const h = Math.floor((m % 1440) / 60);
    const min = (m % 1440) % 60;
    return `${String(h).padStart(2, '0')}:${String(min).padStart(2, '0')}`;
  }

  async function handleTransition() {
    if (!transitionTarget || !queue) return;
    const activeRecipe = dayPlan?.recipe_name;
    if (!activeRecipe) return;

    const newQueue = {
      entries: [
        { recipe: activeRecipe, until: new Date().toISOString().split('T')[0] },
        { transition_to: transitionTarget, days: transitionDays },
        { recipe: transitionTarget },
      ],
    };
    await put('/api/queue', newQueue);
    showTransition = false;
    await load();
  }
</script>

<h1>Light</h1>

{#if dayPlan}
  <section class="active-recipe">
    <h2>Active Recipe: {dayPlan.recipe_name}</h2>
    <p>Photoperiod: {minuteToHHMM(dayPlan.main_on)} &mdash; {minuteToHHMM(dayPlan.main_off)}</p>
    {#if dayPlan.transition_progress !== null}
      <p>Transition: {Math.round(dayPlan.transition_progress * 100)}%</p>
      <progress value={dayPlan.transition_progress} max="1"></progress>
    {/if}
  </section>

  <section>
    <h2>Today's Schedule</h2>
    <div class="timeline">
      <div class="timeline-bar main"
        style="left: {minuteToPercent(dayPlan.main_on)}%; width: {minuteToPercent(dayPlan.main_off - dayPlan.main_on)}%"
        title="Main: {minuteToHHMM(dayPlan.main_on)}-{minuteToHHMM(dayPlan.main_off)}">
      </div>
      {#each dayPlan.channels as ch}
        <div class="timeline-bar channel"
          title="{ch.channel}: {minuteToHHMM(ch.on_time)}-{minuteToHHMM(ch.off_time)}"
          style="left: {minuteToPercent(ch.on_time)}%; width: {minuteToPercent(ch.off_time - ch.on_time)}%">
        </div>
      {/each}
      <div class="timeline-hours">
        {#each Array(24) as _, h}
          <span style="left: {(h / 24) * 100}%">{h}</span>
        {/each}
      </div>
    </div>
  </section>
{:else}
  <p class="muted">No active recipe queue</p>
{/if}

<section>
  <h2>Queue</h2>
  <button onclick={() => showTransition = !showTransition}>Change Recipe</button>
  {#if showTransition}
    <div class="transition-dialog">
      <label>Target recipe:
        <select bind:value={transitionTarget}>
          <option value="">-- select --</option>
          {#each allRecipes as r}
            <option value={r.name}>{r.name}</option>
          {/each}
        </select>
      </label>
      <label>Transition days: <input type="number" bind:value={transitionDays} min="1" max="30" /></label>
      <button onclick={handleTransition} disabled={!transitionTarget}>Apply</button>
    </div>
  {/if}
  {#if queue && queue.entries.length > 0}
    <ul>
      {#each queue.entries as entry}
        <li>
          {#if entry.recipe}
            Recipe: <strong>{entry.recipe}</strong>
            {#if entry.until} until {entry.until}{/if}
          {:else if entry.transition_to}
            Transition to <strong>{entry.transition_to}</strong> ({entry.days} days)
          {/if}
        </li>
      {/each}
    </ul>
  {:else}
    <p class="muted">Queue empty</p>
  {/if}
</section>

<section>
  <h2>Schedule History</h2>
  {#if schedules.length === 0}
    <p class="muted">No schedules</p>
  {:else}
    <table>
      <thead>
        <tr><th>Device</th><th>Date</th><th>On</th><th>Off</th><th>Pushed</th></tr>
      </thead>
      <tbody>
        {#each schedules as s}
          <tr>
            <td>{s.device_id}</td>
            <td>{s.date}</td>
            <td>{s.on_time}</td>
            <td>{s.off_time}</td>
            <td>{s.pushed_at ?? '\u2014'}</td>
          </tr>
        {/each}
      </tbody>
    </table>
  {/if}
</section>

<style>
  .active-recipe { background: #1a1a2e; padding: 1rem; border-radius: 4px; margin-bottom: 1rem; }
  .timeline { position: relative; height: 60px; background: #1a1a2e; border-radius: 4px; margin: 0.5rem 0; overflow: hidden; }
  .timeline-bar { position: absolute; height: 20px; border-radius: 2px; }
  .timeline-bar.main { background: #f0c040; top: 5px; opacity: 0.8; }
  .timeline-bar.channel { background: #40a0f0; top: 30px; opacity: 0.7; }
  .timeline-hours { position: absolute; bottom: 0; width: 100%; height: 15px; }
  .timeline-hours span { position: absolute; font-size: 0.6rem; color: #888; }
  .transition-dialog { border: 1px solid #444; padding: 1rem; margin: 0.5rem 0; border-radius: 4px; }
  .transition-dialog label { display: block; margin: 0.3rem 0; }
  progress { width: 100%; }
</style>
