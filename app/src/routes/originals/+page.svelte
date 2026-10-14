<script lang="ts">
	import { base } from '$app/paths';
	import { normalizeOriginal } from '$lib/search';
	import { BUILD_NAMES, BUILD_ORDER, VENDOR_NAMES, buildsOf, originalsOf, type Build, type Vendor } from '$lib/types';

	let { data } = $props();
	let q = $state('');
	// The list is long (over 4,000 originals): the first rows are in the page, the rest come on request. The filter searches them all.
	const PAGE = 200;
	let shown = $state(PAGE);
	$effect(() => {
		q; // a new filter starts from the top
		shown = PAGE;
	});
	// By name. An original is written maker first ('Boss DS-1', 'Electro-Harmonix Big Muff Pi'), so this is
	// brand, then pedal; numbers compare as numbers (DS-1 before DS-2 before DS-10).
	const byName = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
	const groups = $derived.by(() => {
		const m = new Map<string, { label: string; count: number; builds: Map<Build, number>; vendors: Set<Vendor>; categories: Set<string> }>();
		for (const e of data.index) {
			// a description ('Lots of Big Muff variants') names no original; a board that builds two is counted under each
			for (const original of originalsOf(e)) {
				const k = normalizeOriginal(original);
				if (!k) continue;
				const g = m.get(k) ?? { label: original, count: 0, builds: new Map<Build, number>(), vendors: new Set<Vendor>(), categories: new Set<string>() };
				g.count++;
				for (const b of buildsOf(e)) g.builds.set(b, (g.builds.get(b) ?? 0) + 1); // a PCB with a layout beside it counts under both
				g.vendors.add(e.vendor);
				g.categories.add(e.category);
				m.set(k, g);
			}
		}
		const t = q.trim().toLowerCase();
		return [...m.values()].filter((g) => !t || g.label.toLowerCase().includes(t)).sort((a, b) => byName.compare(a.label, b.label));
	});
</script>

<svelte:head><title>Originals · Akashic</title></svelte:head>

<div class="originals">
	<header class="head">
		<h1>Originals</h1>
		<p class="lede">The commercial pedals these boards are based on, {groups.length.toLocaleString()} listed by name, brand then pedal, with how many circuits clone each and how they are built: on a bought PCB, or from a vero, perfboard, tagboard, turret or point-to-point layout. Pick one to compare every take side by side.</p>
		<label class="filter">
			<span class="label">Filter</span>
			<input type="search" bind:value={q} placeholder="Klon, Rat, Big Muff, Tube Screamer…" autocomplete="off" spellcheck="false" />
		</label>
	</header>
	<table class="sheet-table">
		<thead><tr><th>Original</th><th class="n">Circuits</th><th class="how">Built on</th><th class="src">Sources</th><th class="cat">Category</th></tr></thead>
		<tbody>
			{#each groups.slice(0, shown) as g (g.label)}
				<tr>
					<td><a href="{base}/?based={encodeURIComponent(g.label)}" class="name">{g.label}</a></td>
					<td class="n mono">{g.count}</td>
					<td class="how">{#each BUILD_ORDER.filter((b) => g.builds.has(b)) as b, i}{i ? ' · ' : ''}<a href="{base}/?based={encodeURIComponent(g.label)}&build={b}"><span class="mono">{g.builds.get(b)}</span> {BUILD_NAMES[b]}</a>{/each}</td>
					<td class="src dim">{[...g.vendors].map((v) => VENDOR_NAMES[v]).join(', ')}</td>
					<td class="cat dim">{[...g.categories].join(', ')}</td>
				</tr>
			{/each}
		</tbody>
	</table>
	{#if shown < groups.length}
		<div class="more">
			<button class="btn ghost" type="button" onclick={() => (shown += PAGE * 2)}>Show {Math.min(PAGE * 2, groups.length - shown)} more of {(groups.length - shown).toLocaleString()} remaining</button>
			<button class="btn ghost" type="button" onclick={() => (shown = groups.length)}>Show all</button>
		</div>
	{/if}
</div>

<style>
	.originals { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.lede { max-width: 70ch; color: var(--ink-2); margin-bottom: 16px; }
	.filter { display: flex; align-items: center; gap: 10px; max-width: 460px; margin-bottom: 16px; }
	.filter input { flex: 1; height: 38px; padding: 0 12px; border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet-2); }
	.filter input:focus { outline: none; border-color: var(--coat); box-shadow: 0 0 0 3px var(--coat-tint); background: var(--sheet); }
	.name { font-weight: 600; }
	.more { padding: 16px 10px; display: flex; gap: 10px; flex-wrap: wrap; }
	.dim { color: var(--ink-3); }
	.how { white-space: nowrap; }
	@media (max-width: 900px) { .how { white-space: normal; } }
	@media (max-width: 700px) { .cat, .src { display: none; } }
</style>
