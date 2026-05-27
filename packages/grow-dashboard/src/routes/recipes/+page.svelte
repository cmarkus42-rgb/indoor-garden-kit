<script lang="ts">
  import { get, del, put } from '$lib/api.js';
  import type { RecipesResponse, RecipeSummary, RecipeData } from '$lib/types.js';
  import { onMount } from 'svelte';
  import { goto } from '$app/navigation';

  let recipes = $state<RecipeSummary[]>([]);
  let importJson = $state('');
  let showImport = $state(false);

  async function load() {
    const res = await get<RecipesResponse>('/api/recipes');
    recipes = res.recipes;
  }

  onMount(() => { load(); });

  async function handleDelete(name: string) {
    if (!confirm(`Delete recipe "${name}"?`)) return;
    await del(`/api/recipes/${encodeURIComponent(name)}`);
    await load();
  }

  async function handleClone(name: string) {
    const data = await get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`);
    const cloneName = `${data.name} (Copy)`;
    const cloned: RecipeData = { ...data, name: cloneName };
    await put(`/api/recipes/${encodeURIComponent(cloneName)}`, cloned);
    await load();
  }

  async function handleNew() {
    const name = prompt('Recipe name:');
    if (!name) return;
    const data: RecipeData = {
      name,
      photoperiod: { on: '06:00', off: '00:00' },
      dimming: { sunrise_min: 30, sunset_min: 30, max_pct: 100, min_pct: 0 },
      channels: {},
    };
    await put(`/api/recipes/${encodeURIComponent(name)}`, data);
    goto(`/recipes/${encodeURIComponent(name)}`);
  }

  async function handleImport() {
    try {
      const data = JSON.parse(importJson) as RecipeData;
      await put(`/api/recipes/${encodeURIComponent(data.name)}`, data);
      importJson = '';
      showImport = false;
      await load();
    } catch (e) {
      alert(`Invalid JSON: ${e}`);
    }
  }

  function handleExport(name: string) {
    get<RecipeData>(`/api/recipes/${encodeURIComponent(name)}`).then((data) => {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${name}.json`;
      a.click();
      URL.revokeObjectURL(url);
    });
  }
</script>

<h1>Recipes</h1>

<div class="actions">
  <button onclick={handleNew}>New Recipe</button>
  <button onclick={() => showImport = !showImport}>
    {showImport ? 'Cancel Import' : 'Import JSON'}
  </button>
</div>

{#if showImport}
  <div class="import-box">
    <textarea bind:value={importJson} rows="8" placeholder="Paste recipe JSON..."></textarea>
    <button onclick={handleImport}>Import</button>
  </div>
{/if}

{#if recipes.length === 0}
  <p class="muted">No recipes yet</p>
{:else}
  <table>
    <thead>
      <tr><th>Name</th><th>Photoperiod</th><th>Channels</th><th>Actions</th></tr>
    </thead>
    <tbody>
      {#each recipes as r}
        <tr>
          <td><a href="/recipes/{encodeURIComponent(r.name)}">{r.name}</a></td>
          <td>{r.photoperiod}</td>
          <td>{r.channels}</td>
          <td>
            <button onclick={() => goto(`/recipes/${encodeURIComponent(r.name)}`)}>Edit</button>
            <button onclick={() => handleClone(r.name)}>Clone</button>
            <button onclick={() => handleExport(r.name)}>Export</button>
            <button onclick={() => handleDelete(r.name)}>Delete</button>
          </td>
        </tr>
      {/each}
    </tbody>
  </table>
{/if}

<style>
  .actions { display: flex; gap: 0.5rem; margin-bottom: 1rem; }
  .import-box { margin-bottom: 1rem; }
  .import-box textarea { width: 100%; font-family: monospace; }
</style>
