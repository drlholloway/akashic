<script lang="ts">
	import { base } from '$app/paths';
	import Faceplate from './Faceplate.svelte';
	import { formatPrice } from './data';
	import type { IndexEntry } from './types';
	import { VENDOR_NAMES } from './types';

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
				<th>Based on</th>
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
						{#if e.actives.length}<span class="actives mono">{e.actives.slice(0, 4).join(' · ')}</span>{/if}
					</td>
					<td class="based">
						{#if e.based_on}
							{#if onOriginal}
								<button type="button" class="linkish" onclick={() => onOriginal(e.based_on)} title="Show every circuit based on {e.based_on}">{e.based_on}</button>
							{:else}
								<a href="{base}/?based={encodeURIComponent(e.based_on)}">{e.based_on}</a>
							{/if}
						{:else}
							<span class="dim">—</span>
						{/if}
					</td>
					<td class="cat">{e.category}</td>
					{#if !hideVendor}<td class="vendor">{VENDOR_NAMES[e.vendor]}</td>{/if}
					<td class="enc mono">{e.enclosure || '—'}</td>
					<td class="n knobs mono">{knobCount(e) || '—'}</td>
					<td class="n mono">
						{formatPrice(e.price, e.currency) || '—'}
						{#if e.in_stock === false}<span class="oos" title="Out of stock at the vendor">out</span>{/if}
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
	.wrap { overflow-x: auto; }
	.circuits { min-width: 720px; }
	.glyph { width: 40px; padding-right: 0; }
	.name a { font-weight: 600; }
	.name .sub { color: var(--ink-3); margin-left: 6px; }
	.name .actives { display: block; color: var(--ink-3); font-size: 11.5px; margin-top: 1px; }
	.based { max-width: 26ch; }
	.linkish { background: none; border: 0; padding: 0; cursor: pointer; text-align: left; color: inherit; font: inherit; }
	.linkish:hover { text-decoration: underline; text-underline-offset: 2px; }
	.dim { color: var(--ink-3); }
	.oos { margin-left: 6px; font-family: var(--label); font-size: 10px; letter-spacing: 0.1em; text-transform: uppercase; color: var(--warn); }
	.empty { padding: 32px 10px; color: var(--ink-2); max-width: 60ch; }
	.more { padding: 16px 10px; }
	@media (max-width: 860px) {
		.cat, .bom { display: none; }
	}
</style>
