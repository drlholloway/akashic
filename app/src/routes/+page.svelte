<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import CircuitTable from '$lib/CircuitTable.svelte';
	import { applyFilters, buildSearch, EMPTY_FILTERS, filtersFromParams, paramsFromFilters, type Filters } from '$lib/search';
	import { VENDOR_NAMES, type IndexEntry } from '$lib/types';
	import { currency } from '$lib/currency.svelte';
	import { untrack } from 'svelte';
	import CurrencySelect from '$lib/CurrencySelect.svelte';
	import { controlLabels } from '$lib/controls';
	import { folds } from '$lib/fold.svelte';

	let { data } = $props();
	$effect.pre(() => buildSearch(data.index));
	untrack(() => buildSearch(data.index)); // also during SSR so the first render is searchable (the effect above keeps it current)

	let filters = $state<Filters>({ ...EMPTY_FILTERS });
	let sort = $state<'name' | 'price' | 'bom' | 'vendor'>('name');
	let ready = $state(false);

	$effect(() => {
		if (!browser) return;
		filters = filtersFromParams(page.url.searchParams);
		ready = true;
	});

	function update(patch: Partial<Filters>) {
		const next = { ...filters, ...patch };
		goto(`${base}/?${paramsFromFilters(next).toString()}`, { keepFocus: true, noScroll: true, replaceState: false });
	}
	function toggle(key: 'vendor' | 'category' | 'enclosure', value: string) {
		const cur = filters[key];
		update({ [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] });
	}

	const results = $derived.by(() => {
		const r = applyFilters(data.index, filters);
		const by: Record<typeof sort, (a: IndexEntry, b: IndexEntry) => number> = {
			name: (a, b) => a.name.localeCompare(b.name),
			price: (a, b) => currency.value(a.price, a.currency) - currency.value(b.price, b.currency) || a.name.localeCompare(b.name),
			bom: (a, b) => b.bom_count - a.bom_count || a.name.localeCompare(b.name),
			vendor: (a, b) => a.vendor.localeCompare(b.vendor) || a.name.localeCompare(b.name)
		};
		return filters.q.trim() ? r : [...r].sort(by[sort]);
	});

	// Facet counts computed from the result set with that facet's own filter lifted,
	// so a facet always shows what choosing it would yield.
	function facet(key: 'vendor' | 'category' | 'enclosure'): [string, number][] {
		const lifted = applyFilters(data.index, { ...filters, [key]: [] });
		const m = new Map<string, number>();
		for (const e of lifted) {
			const v = e[key];
			if (!v) continue;
			m.set(v, (m.get(v) ?? 0) + 1);
		}
		return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
	}
	const vendorFacet = $derived(facet('vendor'));
	const categoryFacet = $derived(facet('category'));
	const enclosureFacet = $derived(facet('enclosure').slice(0, 8));
	const knobFacet = $derived.by(() => {
		const lifted = applyFilters(data.index, { ...filters, knobs: null });
		const m = new Map<number, number>();
		for (const e of lifted) {
			const single = e.controls.length === 1 && /^(\d+) knobs?$/.exec(e.controls[0]);
			const n = single ? Number(single[1]) : e.controls.length;
			if (n) m.set(n, (m.get(n) ?? 0) + 1);
		}
		return [...m.entries()].sort((a, b) => a[0] - b[0]);
	});
	// Controls combine with AND (a circuit with both a Blend and a Bias knob), so each count is
	// how many of the current results also have that control; the most common are shown.
	let allControls = $state(false);
	const controlFacet = $derived.by(() => {
		const m = new Map<string, number>();
		for (const e of results) for (const l of controlLabels(e.controls)) m.set(l, (m.get(l) ?? 0) + 1);
		const all = [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
		return allControls ? all : all.filter(([l], i) => i < 12 || filters.control.includes(l));
	});
	function toggleControl(label: string) {
		update({ control: filters.control.includes(label) ? filters.control.filter((c) => c !== label) : [...filters.control, label] });
	}
	const totalVendors = $derived(new Set(data.index.map((e) => e.vendor)).size);
	const shownVendors = $derived(new Set(results.map((e) => e.vendor)).size);
	const active = $derived(
		filters.vendor.length + filters.category.length + filters.enclosure.length + (filters.basedOn ? 1 : 0) + (filters.part ? 1 : 0) + (filters.knobs != null ? 1 : 0) + filters.control.length + (filters.inStock ? 1 : 0)
	);
	// Each filter folds at its header; a folded one still says how many of its choices are on.
	const FACETS = ['vendor', 'category', 'enclosure', 'knobs', 'control'];
	const folded = folds('akashic-filters-folded');
	const allFolded = $derived(FACETS.every((k) => folded.has(k)));
	const chosen = $derived<Record<string, number>>({
		vendor: filters.vendor.length, category: filters.category.length, enclosure: filters.enclosure.length,
		knobs: filters.knobs != null ? 1 : 0, control: filters.control.length
	});
</script>

<svelte:head>
	<title>{filters.q ? `${filters.q} · ` : ''}Circuits · Akashic</title>
</svelte:head>

<div class="index">
	<aside class="facets" aria-label="Filters">
		{#snippet head(key: string, name: string)}
			<h2 class="label strong">
				<button type="button" aria-expanded={!folded.has(key)} aria-controls="facet-{key}" onclick={() => folded.toggle(key)}>
					<span class="chev" aria-hidden="true"></span>{name}{#if chosen[key] && folded.has(key)} <span class="mono on">{chosen[key]} on</span>{/if}
				</button>
			</h2>
		{/snippet}
		<button type="button" class="label all" onclick={() => folded.set(allFolded ? [] : FACETS)}>{allFolded ? 'Expand all' : 'Collapse all'}</button>
		<div class="facet">
			{@render head('vendor', 'Vendor')}
			<div class="chips" id="facet-vendor" hidden={folded.has('vendor')}>
				{#each vendorFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.vendor.includes(v)} onclick={() => toggle('vendor', v)}>{VENDOR_NAMES[v as keyof typeof VENDOR_NAMES] ?? v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			{@render head('category', 'Category')}
			<div class="chips" id="facet-category" hidden={folded.has('category')}>
				{#each categoryFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.category.includes(v)} onclick={() => toggle('category', v)}>{v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			{@render head('enclosure', 'Enclosure')}
			<div class="chips" id="facet-enclosure" hidden={folded.has('enclosure')}>
				{#each enclosureFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.enclosure.includes(v)} onclick={() => toggle('enclosure', v)}>{v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			{@render head('knobs', 'Knobs')}
			<div class="chips" id="facet-knobs" hidden={folded.has('knobs')}>
				{#each knobFacet as [k, n]}
					<button type="button" class="chip" aria-pressed={filters.knobs === k} onclick={() => update({ knobs: filters.knobs === k ? null : k })}>{k} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			{@render head('control', 'Controls')}
			<div class="chips" id="facet-control" hidden={folded.has('control')}>
				{#each controlFacet as [l, n]}
					<button type="button" class="chip" aria-pressed={filters.control.includes(l)} onclick={() => toggleControl(l)}>{l} <span class="count">{n}</span></button>
				{/each}
				<button type="button" class="chip more" onclick={() => (allControls = !allControls)}>{allControls ? 'Fewer' : 'More'}</button>
			</div>
		</div>
		<div class="facet">
			<label class="chip" class:on={filters.inStock}>
				<input type="checkbox" class="sr-only" checked={filters.inStock} onchange={(e) => update({ inStock: e.currentTarget.checked })} />
				In stock only
			</label>
		</div>
	</aside>

	<section class="results">
		<div class="bar">
			<p class="label strong count" aria-live="polite">
				{#if ready}{results.length.toLocaleString()} of {data.index.length.toLocaleString()} circuits · {shownVendors} of {totalVendors} vendors{:else}{data.index.length.toLocaleString()} circuits · {totalVendors} vendors{/if}
			</p>
			<div class="applied">
				{#if filters.q}<button type="button" class="chip on" onclick={() => update({ q: '' })}>“{filters.q}” ×</button>{/if}
				{#if filters.basedOn}<button type="button" class="chip on" onclick={() => update({ basedOn: '' })}>Based on {filters.basedOn} ×</button>{/if}
				{#if filters.part}<button type="button" class="chip on" onclick={() => update({ part: '' })}>Uses {filters.part} ×</button>{/if}
				{#if active || filters.q}<button type="button" class="chip" onclick={() => goto(`${base}/`)}>Clear all</button>{/if}
			</div>
			<CurrencySelect />
			<label class="sort">
				<span class="label">Sort</span>
				<select bind:value={sort} disabled={!!filters.q.trim()}>
					<option value="name">Name</option>
					<option value="vendor">Vendor</option>
					<option value="price">Price</option>
					<option value="bom">BOM size</option>
				</select>
			</label>
		</div>
		<CircuitTable rows={results} onOriginal={(b) => update({ basedOn: b })} />
	</section>
</div>

<style>
	.index { display: grid; grid-template-columns: 260px 1fr; gap: 0; }
	.facets {
		padding: 20px var(--gutter) 20px var(--gutter);
		border-right: 1px solid var(--rule);
		position: sticky;
		top: var(--titleblock-h);
		align-self: start;
		max-height: calc(100dvh - var(--titleblock-h));
		overflow-y: auto;
	}
	.facet { margin-bottom: 20px; }
	.facet h2 { margin-bottom: 4px; }
	.facet h2 button { display: flex; align-items: center; gap: 8px; width: 100%; padding: 4px 0; border: 0; background: none; font: inherit; letter-spacing: inherit; text-transform: inherit; color: inherit; text-align: left; cursor: pointer; }
	.facet h2 button:focus-visible, .all:focus-visible { outline: 2px solid var(--coat); outline-offset: 2px; }
	.facet h2 button:hover .chev { border-color: var(--coat); }
	.chev { width: 6px; height: 6px; border-right: 1.5px solid var(--ink-3); border-bottom: 1.5px solid var(--ink-3); transform: rotate(-45deg); transition: transform 0.12s; flex: none; }
	button[aria-expanded='true'] .chev { transform: rotate(45deg) translate(-1px, -1px); }
	.facet h2 .on { color: var(--coat); font-size: 12px; letter-spacing: 0; text-transform: none; }
	.all { display: block; margin-bottom: 14px; padding: 0; border: 0; background: none; color: var(--ink-2); cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
	.all:hover { color: var(--ink); }
	@media (prefers-reduced-motion: reduce) { .chev { transition: none; } }
	.chips { display: flex; flex-wrap: wrap; gap: 6px; }
	.chips[hidden] { display: none; }
	.chip.more { color: var(--ink-3); }
	.results { min-width: 0; padding: 12px var(--gutter) 24px 0; }
	.bar { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding: 4px 10px 12px; }
	.bar .count { margin: 0; }
	.applied { display: flex; flex-wrap: wrap; gap: 6px; flex: 1; }
	.sort { display: inline-flex; align-items: center; gap: 8px; }
	.sort select { border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet); padding: 4px 8px; }
	@media (max-width: 1000px) {
		.index { grid-template-columns: 1fr; }
		.facets { position: static; max-height: none; border-right: 0; border-bottom: 1px solid var(--rule); padding: 12px 16px; display: flex; flex-wrap: wrap; gap: 8px 24px; }
		.facet { margin: 0; }
		.all { flex-basis: 100%; margin: 0; text-align: left; }
		.results { padding: 8px 16px 24px; }
	}
</style>
