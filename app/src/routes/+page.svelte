<script lang="ts">
	import { browser } from '$app/environment';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import CircuitTable from '$lib/CircuitTable.svelte';
	import { applyFilters, buildSearch, EMPTY_FILTERS, filtersFromParams, paramsFromFilters, type Filters } from '$lib/search';
	import { VENDOR_NAMES, type IndexEntry } from '$lib/types';
	import { currency } from '$lib/currency.svelte';
	import CurrencySelect from '$lib/CurrencySelect.svelte';

	let { data } = $props();
	$effect.pre(() => buildSearch(data.index));
	buildSearch(data.index); // also during SSR so the first render is searchable

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
	const totalVendors = $derived(new Set(data.index.map((e) => e.vendor)).size);
	const shownVendors = $derived(new Set(results.map((e) => e.vendor)).size);
	const active = $derived(
		filters.vendor.length + filters.category.length + filters.enclosure.length + (filters.basedOn ? 1 : 0) + (filters.part ? 1 : 0) + (filters.knobs != null ? 1 : 0) + (filters.inStock ? 1 : 0)
	);
</script>

<svelte:head>
	<title>{filters.q ? `${filters.q} · ` : ''}Circuits · Akashic</title>
</svelte:head>

<div class="index">
	<aside class="facets" aria-label="Filters">
		<div class="facet">
			<h2 class="label strong">Vendor</h2>
			<div class="chips">
				{#each vendorFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.vendor.includes(v)} onclick={() => toggle('vendor', v)}>{VENDOR_NAMES[v as keyof typeof VENDOR_NAMES] ?? v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			<h2 class="label strong">Category</h2>
			<div class="chips">
				{#each categoryFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.category.includes(v)} onclick={() => toggle('category', v)}>{v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			<h2 class="label strong">Enclosure</h2>
			<div class="chips">
				{#each enclosureFacet as [v, n]}
					<button type="button" class="chip" aria-pressed={filters.enclosure.includes(v)} onclick={() => toggle('enclosure', v)}>{v} <span class="count">{n}</span></button>
				{/each}
			</div>
		</div>
		<div class="facet">
			<h2 class="label strong">Knobs</h2>
			<div class="chips">
				{#each knobFacet as [k, n]}
					<button type="button" class="chip" aria-pressed={filters.knobs === k} onclick={() => update({ knobs: filters.knobs === k ? null : k })}>{k} <span class="count">{n}</span></button>
				{/each}
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
	.facet h2 { margin-bottom: 8px; }
	.chips { display: flex; flex-wrap: wrap; gap: 6px; }
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
		.results { padding: 8px 16px 24px; }
	}
</style>
