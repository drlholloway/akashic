<script lang="ts">
	import { base } from '$app/paths';
	import { PART_CATEGORY_NAMES, PART_ORDER } from '$lib/types';

	let { data } = $props();
	let q = $state('');
	const filtered = $derived.by(() => {
		const t = q.trim().toLowerCase();
		return t ? data.parts.filter((p) => p.value.toLowerCase().includes(t) || p.types.some((x) => x.toLowerCase().includes(t))) : data.parts;
	});
	const groups = $derived(
		PART_ORDER.map((k) => ({ key: k, name: PART_CATEGORY_NAMES[k] ?? k, items: filtered.filter((p) => p.category === k) })).filter((g) => g.items.length)
	);
</script>

<svelte:head><title>Parts cross-reference · PCB Schematic Library</title></svelte:head>

<div class="parts-index">
	<header class="head">
		<h1>Parts cross-reference</h1>
		<p class="lede">Every active part value across all vendors' parts lists, with the number of circuits that use it. Pick a part to see what you could build with it. Resistors and capacitors are omitted: they are in everything.</p>
		<label class="filter">
			<span class="label">Filter</span>
			<input type="search" bind:value={q} placeholder="LM308, 2N5088, PT2399, A100k…" autocomplete="off" spellcheck="false" />
		</label>
	</header>
	{#each groups as g}
		<section>
			<h2 class="label strong">{g.name} <span class="mono dim">{g.items.length}</span></h2>
			<ul>
				{#each g.items as p}
					<li>
						<a href="{base}/parts/{p.slug}"><span class="mono val">{p.value}</span><span class="mono n">{p.count}</span></a>
						{#if p.types[0]}<span class="type">{p.types[0]}</span>{/if}
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.parts-index { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.lede { max-width: 70ch; color: var(--ink-2); margin-bottom: 16px; }
	.filter { display: flex; align-items: center; gap: 10px; max-width: 460px; }
	.filter input { flex: 1; height: 38px; padding: 0 12px; border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet-2); }
	.filter input:focus { outline: none; border-color: var(--coat); box-shadow: 0 0 0 3px var(--coat-tint); background: var(--sheet); }
	section { margin-top: 28px; }
	section h2 { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 4px; }
	.dim { color: var(--ink-3); }
	ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 0 24px; }
	li { display: flex; align-items: baseline; gap: 10px; border-bottom: 1px solid var(--rule); padding: 5px 0; min-width: 0; }
	li a { display: inline-flex; gap: 10px; align-items: baseline; }
	.val { font-weight: 600; }
	.n { color: var(--ink-3); font-size: 12px; }
	.type { color: var(--ink-3); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
</style>
