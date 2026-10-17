<script lang="ts">
	import { base } from '$app/paths';
	import Faceplate from './Faceplate.svelte';
	import { currency } from './currency.svelte';
	import { bench } from './bench.svelte';
	import type { IndexEntry } from './types';
	import { BUILD_NAMES, VENDOR_NAMES, buildsOf, originalsOf } from './types';

	interface Props {
		rows: IndexEntry[];
		pageSize?: number;
		onOriginal?: (basedOn: string) => void;
		hideVendor?: boolean;
	}
	let { rows, pageSize = 100, onOriginal, hideVendor = false }: Props = $props();
	let shown = $state(0);
	$effect(() => {
		rows; // reset paging when the result set changes
		shown = pageSize;
	});
	const knobCount = (e: IndexEntry) => {
		const m = e.controls.length === 1 && /^(\d+) knobs?$/.exec(e.controls[0]);
		return m ? Number(m[1]) : e.controls.length;
	};
</script>

<div class="wrap">
	<table class="sheet-table circuits">
		<thead>
			<tr>
				<th class="glyph"><span class="sr-only">Faceplate</span></th>
				<th>Circuit</th>
				<th class="based">Based on</th>
				<th class="cat">Category</th>
				{#if !hideVendor}<th class="vendor">Vendor</th>{/if}
				<th class="enc">Box</th>
				<th class="n knobs">Knobs</th>
				<th class="n">Price</th>
				<th class="n bom">BOM</th>
			</tr>
		</thead>
		<tbody>
			{#each rows.slice(0, shown || pageSize) as e (e.id)}
				<tr>
					<td class="glyph"><Faceplate enclosure={e.enclosure} controls={e.controls} size={30} /></td>
					<td class="name">
						<a href="{base}/circuit/{e.file_id}">{e.name}</a>
						{#if e.subtitle}<span class="sub">{e.subtitle}</span>{/if}
						{#each buildsOf(e).filter((b) => b !== 'pcb') as b}<span class="build" title={e.verified === true ? 'Layout marked verified by its source' : e.verified === false ? 'Layout not yet verified by a build' : undefined}>{BUILD_NAMES[b]}{#if e.board && b === buildsOf(e)[0]} {e.board.replace('x', '×')}{/if}</span>{/each}
						{#if bench.has(e.id)}<span class="build on-bench" title="On my bench">Bench</span>{/if}
						{#if e.verified === true}<span class="build ok" title="The layout's source marks it as verified: someone has built it and it works">Verified</span>{:else if e.verified === false}<span class="build no" title="No working build of this layout has been reported at its source yet">Unverified</span>{/if}
						{#if e.actives.length}<span class="actives mono">{e.actives.slice(0, 4).join(' · ')}</span>{/if}
						{#if e.based_on || e.enclosure}<span class="folded">{[originalsOf(e).join(' / ') || e.based_on, e.enclosure].filter(Boolean).join(' · ')}</span>{/if}
					</td>
					<td class="based">
						{#if e.original}
							{#each originalsOf(e) as o, n}
								{#if n}<span class="dim">{' · '}</span>{/if}
								{#if onOriginal}
									<button type="button" class="linkish" onclick={() => onOriginal(o)} title="Show every circuit based on the {o}">{o}</button>
								{:else}
									<a href="{base}/?based={encodeURIComponent(o)}">{o}</a>
								{/if}
							{/each}
						{:else if e.based_on}
							<span class="dim">{e.based_on}</span>
						{:else}
							<span class="dim">—</span>
						{/if}
					</td>
					<td class="cat">{e.category}</td>
					{#if !hideVendor}<td class="vendor">{VENDOR_NAMES[e.vendor]}</td>{/if}
					<td class="enc mono">{e.enclosure || '—'}</td>
					<td class="n knobs mono">{knobCount(e) || '—'}</td>
					<td class="n mono" title={e.price != null && currency.convert(e.price, e.currency).converted ? `${currency.native(e.price, e.currency)} at ${VENDOR_NAMES[e.vendor]}` : undefined}>
						{currency.format(e.price, e.currency) || '—'}
						{#if e.delisted}<span class="oos" title="No longer listed by the vendor (since {e.delisted})">delisted</span>{:else if e.in_stock === false}<span class="oos" title="Out of stock at the vendor">out</span>{/if}
					</td>
					<td class="n bom mono">{e.bom_count || '—'}</td>
				</tr>
			{/each}
		</tbody>
	</table>
	{#if rows.length === 0}
		<p class="empty">Nothing matches. Clear a filter or try a looser search: the original's name, a part number like <span class="mono">PT2399</span>, or an enclosure like <span class="mono">125B</span>.</p>
	{/if}
	{#if (shown || pageSize) < rows.length}
		<div class="more">
			<button class="btn ghost" type="button" onclick={() => (shown += pageSize * 2)}>Show {Math.min(pageSize * 2, rows.length - shown)} more of {rows.length - shown} remaining</button>
		</div>
	{/if}
</div>

<style>
	/* The column header is sticky against the page, so the table is never put in a scroll
	   container: on narrow screens columns fold into the name cell instead of scrolling sideways. */
	.circuits { width: 100%; }
	.glyph { width: 40px; padding-right: 0; }
	.name a { font-weight: 600; }
	.name .sub { color: var(--ink-3); margin-left: 6px; }
	.name .actives { display: block; color: var(--ink-3); font-size: 11.5px; margin-top: 1px; }
	.name .folded { display: none; color: var(--ink-2); font-size: 12px; margin-top: 2px; }
	.based { max-width: 26ch; }
	.linkish { background: none; border: 0; padding: 0; cursor: pointer; text-align: left; color: inherit; font: inherit; }
	.linkish:hover { text-decoration: underline; text-underline-offset: 2px; }
	.dim { color: var(--ink-3); }
	.build { margin-left: 6px; font-family: var(--label); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--ink-2); border: 1px solid var(--rule-strong); border-radius: 3px; padding: 0 4px; white-space: nowrap; }
	.build.ok { color: var(--coat); border-color: var(--coat); }
	.build.no { color: var(--warn); border-color: currentColor; }
	.build.on-bench { color: var(--ink); background: var(--coat-tint); border-color: var(--coat); }
	.oos { margin-left: 6px; font-family: var(--label); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--warn); }
	.empty { padding: 32px 10px; color: var(--ink-2); max-width: 60ch; }
	.more { padding: 16px 10px; }
	@media (max-width: 1000px) {
		.based { max-width: 18ch; }
	}
	@media (max-width: 860px) {
		.cat, .bom { display: none; }
	}
	@media (max-width: 640px) {
		.based, .enc, .knobs { display: none; }
		.name .folded { display: block; }
		.circuits :global(td), .circuits :global(th) { padding-left: 6px; padding-right: 6px; }
		.glyph { width: 34px; }
	}
</style>
