<script lang="ts">
	import { base } from '$app/paths';
	import CircuitTable from '$lib/CircuitTable.svelte';
	import { PART_CATEGORY_NAMES, type TransistorSpec } from '$lib/types';
	let { data } = $props();
	const subs = $derived(data.subs);
	const isFet = $derived(subs?.kind === 'jfet' || subs?.kind === 'mosfet');
	const kindLabel = $derived(
		!subs ? '' : subs.kind === 'bjt' ? `${subs.mat ?? ''} ${subs.pol ?? ''} transistor`.trim() : `${subs.ch ?? ''}-channel ${subs.kind === 'jfet' ? 'JFET' : 'MOSFET'}`
	);
	const fmt = (v: number | undefined, unit: string, scale = 1) => (v == null ? '' : `${Number((v * scale).toPrecision(3))}${unit}`);
	const cols = $derived(
		isFet
			? [
					{ h: subs?.kind === 'mosfet' ? 'Vgs(th)' : 'Vgs max', f: (s: TransistorSpec) => fmt(subs?.kind === 'mosfet' ? s.vgsth : s.vgs, ' V') },
					{ h: 'Id max', f: (s: TransistorSpec) => fmt(s.idmax, ' mA', 1000) },
					{ h: 'Vds', f: (s: TransistorSpec) => fmt(s.vds, ' V') },
					{ h: 'Pd', f: (s: TransistorSpec) => fmt(s.pd, ' W') }
				]
			: [
					{ h: 'hFE min', f: (s: TransistorSpec) => fmt(s.hfe, '') },
					{ h: 'Vce', f: (s: TransistorSpec) => fmt(s.vce, ' V') },
					{ h: 'Ic', f: (s: TransistorSpec) => fmt(s.ic, ' mA', 1000) },
					{ h: 'Pc', f: (s: TransistorSpec) => fmt(s.pc, ' W') },
					{ h: 'fT', f: (s: TransistorSpec) => fmt(s.ft, ' MHz') }
				]
	);
	const slugOf = (pn: string) => (data.partSlugs as Record<string, string>)[pn.toUpperCase()];
</script>

<svelte:head><title>{data.part.value} · circuits using it · Akashic</title></svelte:head>

<div class="part">
	<header class="head">
		<p class="label"><a href="{base}/parts">Parts</a> · {PART_CATEGORY_NAMES[data.part.category] ?? data.part.category}</p>
		<h1 class="mono">{data.part.value}</h1>
		<p class="lede">{data.rows.length} {data.rows.length === 1 ? 'circuit uses' : 'circuits use'} this part{#if data.part.types.length}. Listed as: {data.part.types.join('; ')}{/if}.</p>
	</header>
	{#if subs}
		<section class="subs">
			<h2 class="label strong">Substitutes <span class="dim">{kindLabel}</span></h2>
			<p class="note">Matched on material, polarity and the limits below from the transistor parameter database. Pinouts and packages are not in that data: check the datasheet before you drop one in, and expect gain to change the sound.</p>
			{#snippet table(rows: TransistorSpec[], showBoards: boolean)}
				<table class="sheet-table subs-table">
					<thead><tr><th>Part</th>{#each cols as c}<th class="num">{c.h}</th>{/each}{#if showBoards}<th class="num">Boards</th>{/if}</tr></thead>
					<tbody>
						{#each rows as s}
							<tr>
								<td class="mono">{#if slugOf(s.pn)}<a href="{base}/parts/{slugOf(s.pn)}">{s.pn}</a>{:else}{s.pn}{/if}</td>
								{#each cols as c}<td class="mono num">{c.f(s)}</td>{/each}
								{#if showBoards}<td class="mono num">{s.boards}</td>{/if}
							</tr>
						{/each}
					</tbody>
				</table>
			{/snippet}
			<div class="subs-grid">
				<div>
					<h3 class="label">This part</h3>
					{@render table([subs.spec], false)}
				</div>
				{#if subs.used.length}
					<div>
						<h3 class="label">Used on other boards here</h3>
						{@render table(subs.used, true)}
					</div>
				{/if}
				{#if subs.closest.length}
					<div>
						<h3 class="label">Closest by the numbers</h3>
						{@render table(subs.closest, false)}
					</div>
				{/if}
			</div>
		</section>
	{/if}
	<CircuitTable rows={data.rows} />
</div>

<style>
	.part { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head { margin-bottom: 16px; }
	.head h1 { font-size: clamp(30px, 4.5vw, 44px); margin: 4px 0 8px; font-family: var(--mono); font-weight: 600; letter-spacing: 0; }
	.lede { color: var(--ink-2); max-width: 70ch; }
	.subs { margin: 8px 0 28px; }
	.subs .note { color: var(--ink-2); max-width: 78ch; margin: 4px 0 12px; font-size: 14px; line-height: 1.45; }
	.subs-grid { display: grid; gap: 16px 28px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
	.subs-grid h3 { margin: 0 0 6px; }
	.subs-table td.num, .subs-table th.num { text-align: right; }
	.subs-table { width: 100%; }
</style>
