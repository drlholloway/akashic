<script lang="ts">
	import { base } from '$app/paths';
	import { folds } from '$lib/fold.svelte';
	import { PART_CATEGORY_NAMES, PART_ORDER } from '$lib/types';

	let { data } = $props();
	let q = $state('');
	const filtered = $derived.by(() => {
		const t = q.trim().toLowerCase();
		return t ? data.parts.filter((p) => p.value.toLowerCase().includes(t) || p.types.some((x) => x.toLowerCase().includes(t)) || (p.desc ?? '').toLowerCase().includes(t)) : data.parts;
	});
	// Alphabetical within each category, numbers compared as numbers: A10k before A100k, 2N3904 before 2N5088.
	const byValue = new Intl.Collator('en', { numeric: true, sensitivity: 'base' });
	const groups = $derived(
		PART_ORDER.map((k) => ({
			key: k,
			name: PART_CATEGORY_NAMES[k] ?? k,
			items: filtered.filter((p) => p.category === k).sort((a, b) => byValue.compare(a.value, b.value))
		})).filter((g) => g.items.length)
	);

	// Sections fold at their header. The choice is kept in this browser; a filter opens every
	// section, so a match is never hidden in a folded one.
	const folded = folds('akashic-parts-folded');
	const filtering = $derived(q.trim() !== '');
	const open = (k: string) => filtering || !folded.has(k);
	const allFolded = $derived(groups.every((g) => folded.has(g.key)));

	// Pots are grouped by taper, then ordered by resistance: A1k, A10k, A100k, A1M.
	const TAPERS: [string, string][] = [['A', 'A · log'], ['B', 'B · linear'], ['C', 'C · reverse log'], ['W', 'W'], ['', 'No taper given']];
	const POT_VALUE = /^([A-Z]?)(\d+(?:\.\d+)?)(k|M)?$/;
	function potGroups<T extends { value: string }>(items: T[]) {
		const ohms = (v: string) => {
			const m = v.match(POT_VALUE);
			return m ? parseFloat(m[2]) * (m[3] === 'M' ? 1e6 : m[3] === 'k' ? 1e3 : 1) : Infinity;
		};
		const taper = (v: string) => v.match(POT_VALUE)?.[1] ?? null;
		const groups = TAPERS.map(([t, name]) => ({
			name,
			items: items.filter((p) => taper(p.value) === t).sort((a, b) => ohms(a.value) - ohms(b.value))
		}));
		const other = items.filter((p) => taper(p.value) === null);  // already alphabetical
		if (other.length) groups.push({ name: 'Other', items: other });
		return groups.filter((g) => g.items.length);
	}

	// Columns sized to a section's longest part number and count (both monospace), so every
	// description in the section starts at the same place, and room for nine in ten of its
	// descriptions (set smaller, so about 0.8ch a letter). A very long value wraps.
	function cols(items: { value: string; count: number; desc?: string; types: string[] }[]) {
		const vw = Math.min(16, Math.max(...items.map((p) => p.value.length)));
		const nw = Math.max(...items.map((p) => String(p.count).length));
		const lens = items.map((p) => (p.desc ?? p.types[0] ?? '').length).sort((a, b) => a - b);
		const dw = Math.max(16, Math.min(44, Math.ceil(lens[Math.floor(lens.length * 0.9)] * 0.8)));
		return `--vw: ${vw}ch; --nw: ${nw}ch; --dw: ${dw}ch`;
	}
</script>

<svelte:head><title>Parts cross-reference · Akashic</title></svelte:head>

<div class="parts-index">
	<header class="head">
		<h1>Parts cross-reference</h1>
		<p class="lede">Every active part value across all vendors' parts lists, with the number of circuits that use it. Pick a part to see what you could build with it. Resistors and capacitors are omitted: they are in everything.</p>
		<p class="lede">A part's page links its datasheet when one is available: the maker's own copy, or an archived copy for a discontinued part the maker no longer publishes. Transistors also list possible substitutes, matched on material, polarity and ratings.</p>
		<label class="filter">
			<span class="label">Filter</span>
			<input type="search" bind:value={q} placeholder="LM308, 2N5088, PT2399, A100k…" autocomplete="off" spellcheck="false" />
		</label>
		{#if !filtering}
			<button type="button" class="label all" onclick={() => folded.set(allFolded ? [] : PART_ORDER.slice())}>{allFolded ? 'Expand all' : 'Collapse all'}</button>
		{/if}
	</header>
	{#each groups as g}
		<section>
			<h2 class="label strong">
				<button type="button" aria-expanded={open(g.key)} aria-controls="parts-{g.key}" disabled={filtering} onclick={() => folded.toggle(g.key)}>
					<span class="chev" aria-hidden="true"></span>{g.name} <span class="mono dim">{g.items.length}</span>
				</button>
			</h2>
			<div id="parts-{g.key}" hidden={!open(g.key)}>
			{#if g.key === 'POT'}
				{#each potGroups(g.items) as sub}
					<h3 class="label sub">{sub.name} <span class="mono dim">{sub.items.length}</span></h3>
					<ul style={cols(g.items)}>
						{#each sub.items as p}
							<li>
								<a href="{base}/parts/{p.slug}"><span class="mono val">{p.value}</span><span class="mono n">{p.count}</span></a>
								{#if p.desc ?? p.types[0]}<span class="type">{p.desc ?? p.types[0]}</span>{/if}
							</li>
						{/each}
					</ul>
				{/each}
			{:else}
				<ul style={cols(g.items)}>
					{#each g.items as p}
						<li>
							<a href="{base}/parts/{p.slug}"><span class="mono val">{p.value}</span><span class="mono n">{p.count}</span></a>
							{#if p.desc ?? p.types[0]}<span class="type">{p.desc ?? p.types[0]}</span>{/if}
						</li>
					{/each}
				</ul>
			{/if}
			</div>
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
	section h2 { border-bottom: 1px solid var(--rule-strong); margin-bottom: 4px; }
	section h2 button { display: flex; align-items: center; gap: 8px; width: 100%; padding: 6px 0; border: 0; background: none; font: inherit; letter-spacing: inherit; text-transform: inherit; color: inherit; text-align: left; cursor: pointer; }
	section h2 button:disabled { cursor: default; }
	section h2 button:focus-visible, .all:focus-visible { outline: 2px solid var(--coat); outline-offset: 2px; }
	section h2 button:not(:disabled):hover .chev { border-color: var(--coat); }
	.chev { width: 6px; height: 6px; border-right: 1.5px solid var(--ink-3); border-bottom: 1.5px solid var(--ink-3); transform: rotate(-45deg); transition: transform 0.12s; flex: none; }
	button[aria-expanded='true'] .chev { transform: rotate(45deg) translate(-1px, -1px); }
	button:disabled .chev { visibility: hidden; }
	.all { margin-top: 14px; padding: 0; border: 0; background: none; color: var(--ink-2); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
	.all:hover { color: var(--ink); }
	@media (prefers-reduced-motion: reduce) { .chev { transition: none; } }
	.dim { color: var(--ink-3); }
	h3.sub { margin: 14px 0 2px; color: var(--ink-2); }
	ul { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(min(100%, calc(var(--vw) + var(--nw) + var(--dw))), 1fr)); gap: 0 28px; }
	li { display: grid; grid-template-columns: var(--vw) var(--nw) minmax(0, 1fr); column-gap: 10px; align-items: baseline; border-bottom: 1px solid var(--rule); padding: 5px 0; min-width: 0; }
	li a { display: grid; grid-column: 1 / 3; grid-template-columns: subgrid; align-items: baseline; min-width: 0; }
	.val { font-weight: 600; overflow-wrap: anywhere; }
	.n { color: var(--ink-3); font-size: 12px; text-align: right; }
	.type { color: var(--ink-3); font-size: 12px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	@media (max-width: 600px) {
		li { grid-template-columns: min(var(--vw), 11ch) var(--nw) minmax(0, 1fr); }
		.type { white-space: normal; }
	}
</style>
