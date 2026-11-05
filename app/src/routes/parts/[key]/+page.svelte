<script lang="ts">
	import { base } from '$app/paths';
	import CircuitTable from '$lib/CircuitTable.svelte';
	import { PART_CATEGORY_NAMES, type PartSpec, type TransistorSpec } from '$lib/types';
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
	// Datasheet substitutes: the columns that matter for each kind of socket
	const ss = $derived(data.specSubs);
	const g = $derived(ss?.group ?? '');
	const num = (v: number | undefined, unit = '') => (v == null ? '' : `${Number(v.toPrecision(3))}${unit}`);
	const supply = (s: PartSpec) => (s.vmin == null && s.vmax == null ? '' : `${s.vmin ?? '?'}–${s.vmax ?? '?'} V`);
	const ohms = (v: number | undefined) => (v == null ? '' : v >= 1e6 ? `${num(v / 1e6)}M` : v >= 1e3 ? `${num(v / 1e3)}k` : `${num(v)}`);
	const specCols = $derived.by((): { h: string; f: (s: PartSpec) => string; text?: boolean }[] => {
		if (/^(opamp|ota|cmp)/.test(g))
			return [
				{ h: 'Input', f: (s) => [s.input === 'jfet' ? 'JFET' : s.input === 'cmos' ? 'CMOS' : s.input ?? '', s.rr ? `RR ${s.rr}` : ''].filter(Boolean).join(', '), text: true },
				{ h: 'Supply', f: supply },
				{ h: 'GBW', f: (s) => num(s.gbw, ' MHz') },
				{ h: 'Slew', f: (s) => num(s.slew, ' V/µs') },
				{ h: 'Noise', f: (s) => num(s.noise, ' nV') },
				{ h: 'Iq', f: (s) => num(s.iq, ' mA') }
			];
		if (g.startsWith('reg'))
			return [
				{ h: 'Vout', f: (s) => num(s.vout, ' V') },
				{ h: 'Iout', f: (s) => num(s.iout, ' A') },
				{ h: 'Dropout', f: (s) => num(s.vdrop, ' V') },
				{ h: 'Vin max', f: (s) => num(s.vmax, ' V') }
			];
		if (g.startsWith('chargepump'))
			return [
				{ h: 'Supply', f: supply },
				{ h: 'Iout', f: (s) => num(s.iout, ' mA') },
				{ h: 'Osc', f: (s) => num(s.fosc, ' kHz') }
			];
		if (g.startsWith('bbd'))
			return [
				{ h: 'Stages', f: (s) => num(s.stages) },
				{ h: 'Supply', f: supply },
				{ h: 'Clock max', f: (s) => num(s.clock, ' kHz') }
			];
		if (g.startsWith('zener'))
			return [
				{ h: 'Vz', f: (s) => num(s.vz, ' V') },
				{ h: 'Power', f: (s) => num(s.pd, ' W') },
				{ h: 'Package', f: (s) => s.package ?? '', text: true }
			];
		if (ss?.kind === 'diode')
			return [
				{ h: 'Vf', f: (s) => (s.vf == null ? '' : `${num(s.vf, ' V')}${s.vf_if != null ? ` @ ${num(s.vf_if)} mA` : ''}`) },
				{ h: 'If max', f: (s) => num(s.ifmax, ' A') },
				{ h: 'Vr', f: (s) => num(s.vr, ' V') },
				{ h: 'trr', f: (s) => num(s.trr, ' ns') },
				{ h: 'Cj', f: (s) => num(s.cj, ' pF') },
				{ h: 'Package', f: (s) => s.package ?? '', text: true }
			];
		if (ss?.kind === 'opto')
			return [
				{ h: 'On', f: (s) => (s.ron == null ? '' : `${ohms(s.ron)}${s.ron_if != null ? ` @ ${num(s.ron_if)} mA` : ''}`) },
				{ h: 'Dark', f: (s) => ohms(s.roff) },
				{ h: 'Rise', f: (s) => num(s.rise, ' ms') },
				{ h: 'Decay', f: (s) => num(s.fall, ' ms') }
			];
		return [{ h: 'Supply', f: supply }];
	});
	const slugOf = (pn: string) => (data.partSlugs as Record<string, string>)[pn.toUpperCase()];
</script>

<svelte:head><title>{data.part.value} · circuits using it · Akashic</title></svelte:head>

<div class="part">
	<header class="head">
		<p class="label"><a href="{base}/parts">Parts</a> · {PART_CATEGORY_NAMES[data.part.category] ?? data.part.category}</p>
		<h1 class="mono">{data.part.value}</h1>
		<p class="lede">{#if data.part.desc}{data.part.desc}. {/if}{data.rows.length} {data.rows.length === 1 ? 'circuit uses' : 'circuits use'} this part{#if data.part.types.length}. Listed as: {data.part.types.join('; ')}{/if}.</p>
		{#if (data.part.datasheets?.length ?? 0) > 1}
			{@const sheets = data.part.datasheets ?? []}
			{@const reissued = /^https?:/.test(sheets[0].href)}
			<p class="sheet">Datasheets: {#each sheets as d, i}{#if i}<span class="dim">{' · '}</span>{/if}<a href={/^https?:/.test(d.href) ? d.href : `${base}/${d.href}`} target="_blank" rel="noopener">{d.maker || `copy ${i + 1}`}{d.selector ? ' (selector table)' : ''}</a>{/each} <span class="dim">· {reissued ? 'the original is discontinued and made again under another number; its archived sheet follows' : `archived copies from ${sheets.length} fabs; the part is discontinued and the makers no longer publish it`}</span></p>
		{:else if data.part.datasheet}
			{@const maker = data.part.datasheets?.[0]?.maker}
			{@const hosted = !/^https?:/.test(data.part.datasheet)}
			<p class="sheet"><a href={hosted ? `${base}/${data.part.datasheet}` : data.part.datasheet} target="_blank" rel="noopener">{data.part.selector ? 'Selector table' : 'Datasheet'}</a> <span class="dim">· {data.part.selector ? 'a row in a maker\'s catalog, not a full datasheet; the part is discontinued' : hosted ? `archived copy${maker ? ` from ${maker}` : ''}; ${data.part.sheet_only ? 'kept here as it was not found on the maker\'s own site' : 'the part is discontinued and the maker no longer publishes it'}` : `${maker ? `${maker} · ` : ''}from ${new URL(data.part.datasheet).hostname.replace(/^www\./, '')}`}</span></p>
		{/if}
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
					{#if subs.anchor}
						<p class="note">The database does not list this number. The parameters and matches are those of the {subs.anchor}, its closest listed equivalent.</p>
					{/if}
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
	{#if ss}
		<section class="subs">
			<h2 class="label strong">Substitutes <span class="dim">{ss.kind === 'ic' ? 'same socket' : g.startsWith('zener') ? 'same voltage' : 'same kind'}</span></h2>
			<p class="note">{#if ss.kind === 'ic'}Parts that fit the same socket: the same function, pin count and pinout.{:else if g.startsWith('zener')}Zeners of the same voltage.{:else if ss.kind === 'opto'}Optocouplers and photoresistors of the same construction; the response speed and resistance range set how an effect sounds.{:else}Diodes of the same kind; for clipping, the forward drop is what you hear.{/if}
				The figures are read off each part's datasheet{ss.page ? ` (this one's from page ${ss.page})` : ''}, typical where the sheet gives a typical value, otherwise the maximum. Closest first; the last column says what differs. A different part can change the sound, and a circuit may lean on one particular figure, so read the build document's notes before you swap.</p>
			{#snippet specTable(rows: PartSpec[], other: boolean)}
				<div class="scroll"><table class="sheet-table subs-table">
					<thead><tr><th>Part</th>{#each specCols as c}<th class={c.text ? '' : 'num'}>{c.h}</th>{/each}<th class="num">Boards</th>{#if other}<th>Differs</th>{/if}</tr></thead>
					<tbody>
						{#each rows as s}
							<tr>
								<td class="mono">{#if slugOf(s.pn) && s.pn !== data.part.value}<a href="{base}/parts/{slugOf(s.pn)}">{s.pn}</a>{:else}{s.pn}{/if}</td>
								{#each specCols as c}<td class="mono" class:num={!c.text}>{c.f(s)}</td>{/each}
								<td class="mono num">{s.boards || ''}</td>
								{#if other}<td class="diff">{(s.diff ?? []).join('; ')}{#if s.notes}<span class="dim">{s.diff?.length ? '. ' : ''}{s.notes}</span>{/if}</td>{/if}
							</tr>
						{/each}
					</tbody>
				</table></div>
			{/snippet}
			<h3 class="label">This part</h3>
			{@render specTable([{ ...ss.spec, boards: ss.boards }], false)}
			{#if ss.notes}<p class="note">{ss.notes}</p>{/if}
			<h3 class="label">{ss.kind === 'ic' ? 'Fits the same socket' : 'Alternatives'}</h3>
			{@render specTable(ss.subs, true)}
		</section>
	{/if}
	{#if data.part.zeners?.length}
		<section class="subs">
			<h2 class="label strong">Zeners for {data.part.value.replace('V', '.').replace(/\.$/, '')} V</h2>
			<p class="note">The parts list gives only the voltage, so any zener of that voltage fits. A 500 mW part in DO-35 suits clipping and most pedal uses; the 1 W and 1.3 W parts are larger (DO-41) and only needed where the zener carries real current, such as clamping a supply rail. Check the spacing on the board before ordering the bigger body.{#if parseFloat(data.part.value.replace('V', '.')) < 2.4} Below 2.4 V only the low-level 1N4678 series is made; a plain (not high-brightness) red LED drops about 1.8 V and is the common stand-in.{/if}</p>
			<div class="scroll"><table class="sheet-table subs-table">
				<thead><tr><th>Part</th><th>Series</th><th>Power</th><th>Package</th><th class="num">Boards</th><th>Datasheet</th></tr></thead>
				<tbody>
					{#each data.part.zeners as z}
						<tr>
							<td class="mono">{#if data.zeners[z.pn]?.slug}<a href="{base}/parts/{data.zeners[z.pn].slug}">{z.pn}</a>{:else}{z.pn}{/if}</td>
							<td class="mono">{z.series}</td>
							<td class="mono">{z.power}</td>
							<td class="mono">{z.package}</td>
							<td class="mono num">{data.zeners[z.pn]?.boards || ''}</td>
							<td><a href={z.datasheet} target="_blank" rel="noopener">{new URL(z.datasheet).hostname.replace(/^(www|my|assets)\./, '')}</a></td>
						</tr>
					{/each}
				</tbody>
			</table></div>
		</section>
	{/if}
	<CircuitTable rows={data.rows} />
</div>

<style>
	.part { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head { margin-bottom: 16px; }
	.head h1 { font-size: clamp(30px, 4.5vw, 44px); margin: 4px 0 8px; font-family: var(--mono); font-weight: 600; letter-spacing: 0; }
	.lede { color: var(--ink-2); max-width: 70ch; }
	.sheet { margin-top: 6px; }
	.sheet a { font-weight: 600; }
	.subs { margin: 8px 0 28px; }
	.subs .note { color: var(--ink-2); max-width: 78ch; margin: 4px 0 12px; font-size: 14px; line-height: 1.45; }
	.subs-grid { display: grid; gap: 16px 28px; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); }
	.subs-grid h3 { margin: 0 0 6px; }
	.subs-table td.num, .subs-table th.num { text-align: right; }
	.subs-table { width: 100%; }
	.scroll { overflow-x: auto; }
	.subs h3 { margin: 12px 0 6px; }
	/* short tables in a horizontal scroller: a sticky header would stick to the scroller, not the page */
	.subs .scroll .subs-table th { position: static; }
	.subs-table td.num { white-space: nowrap; }
	.subs-table td.diff { color: var(--ink-2); font-size: 13px; min-width: 18ch; }
</style>
