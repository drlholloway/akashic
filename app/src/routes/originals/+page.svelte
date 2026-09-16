<script lang="ts">
	import { base } from '$app/paths';
	import { normalizeOriginal } from '$lib/search';
	import { VENDOR_NAMES, type Vendor } from '$lib/types';

	let { data } = $props();
	let q = $state('');
	const groups = $derived.by(() => {
		const m = new Map<string, { label: string; count: number; vendors: Set<Vendor>; categories: Set<string> }>();
		for (const e of data.index) {
			if (!e.based_on) continue;
			const k = normalizeOriginal(e.based_on);
			if (!k) continue;
			const g = m.get(k) ?? { label: e.based_on, count: 0, vendors: new Set<Vendor>(), categories: new Set<string>() };
			g.count++;
			g.vendors.add(e.vendor);
			g.categories.add(e.category);
			if (e.based_on.length < g.label.length) g.label = e.based_on; // prefer the shortest spelling
			m.set(k, g);
		}
		const t = q.trim().toLowerCase();
		return [...m.values()].filter((g) => !t || g.label.toLowerCase().includes(t)).sort((a, b) => b.count - a.count || a.label.localeCompare(b.label));
	});
</script>

<svelte:head><title>Originals · PCB Schematic Library</title></svelte:head>

<div class="originals">
	<header class="head">
		<h1>Originals</h1>
		<p class="lede">The commercial pedals these boards are based on, ranked by how many boards clone them. Pick one to compare every vendor's take side by side.</p>
		<label class="filter">
			<span class="label">Filter</span>
			<input type="search" bind:value={q} placeholder="Klon, Rat, Big Muff, Tube Screamer…" autocomplete="off" spellcheck="false" />
		</label>
	</header>
	<table class="sheet-table">
		<thead><tr><th>Original</th><th class="n">Boards</th><th>Vendors</th><th class="cat">Category</th></tr></thead>
		<tbody>
			{#each groups as g (g.label)}
				<tr>
					<td><a href="{base}/?based={encodeURIComponent(g.label)}" class="name">{g.label}</a></td>
					<td class="n mono">{g.count}</td>
					<td class="dim">{[...g.vendors].map((v) => VENDOR_NAMES[v]).join(', ')}</td>
					<td class="cat dim">{[...g.categories].join(', ')}</td>
				</tr>
			{/each}
		</tbody>
	</table>
</div>

<style>
	.originals { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.lede { max-width: 70ch; color: var(--ink-2); margin-bottom: 16px; }
	.filter { display: flex; align-items: center; gap: 10px; max-width: 460px; margin-bottom: 16px; }
	.filter input { flex: 1; height: 38px; padding: 0 12px; border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet-2); }
	.filter input:focus { outline: none; border-color: var(--coat); box-shadow: 0 0 0 3px var(--coat-tint); background: var(--sheet); }
	.name { font-weight: 600; }
	.dim { color: var(--ink-3); }
	@media (max-width: 700px) { .cat { display: none; } }
</style>
