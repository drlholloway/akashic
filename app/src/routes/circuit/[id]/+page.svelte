<script lang="ts">
	import { base } from '$app/paths';
	import Faceplate from '$lib/Faceplate.svelte';
	import { currency } from '$lib/currency.svelte';
	import { normalizeOriginal } from '$lib/search';
	import { PART_CATEGORY_NAMES, PART_ORDER, VENDOR_NAMES, VENDOR_KIND, primaryAction, type BomRow } from '$lib/types';

	let { data } = $props();
	const c = $derived(data.circuit);
	const siblings = $derived(
		c.based_on
			? data.index.filter((e) => e.id !== c.id && e.based_on && normalizeOriginal(e.based_on) === normalizeOriginal(c.based_on))
			: []
	);
	const groups = $derived.by(() => {
		const m = new Map<string, BomRow[]>();
		for (const r of c.bom) {
			const k = r.category || 'OTHER';
			if (!m.has(k)) m.set(k, []);
			m.get(k)!.push(r);
		}
		return PART_ORDER.filter((k) => m.has(k)).map((k) => ({ key: k, name: PART_CATEGORY_NAMES[k] ?? k, rows: m.get(k)! }));
	});
	const XREF = new Set(['IC', 'Q', 'D', 'OPTO', 'POT', 'TRIM', 'SW', 'LED', 'L', 'XTAL']);
	const partSlug = (r: BomRow) => `${r.category}:${r.norm_value}`.toLowerCase().replace(/[^a-z0-9.]+/g, '-');

	let copied = $state(false);
	async function copyBom() {
		const tsv = ['Ref\tValue\tType\tNotes', ...c.bom.map((r) => [r.ref, r.value, r.part_type, r.notes].join('\t'))].join('\n');
		await navigator.clipboard.writeText(tsv);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
	const knobs = $derived(c.controls.filter((x) => !/^\d+ knobs?$/.test(x)));
	const schematicImage = $derived((c as unknown as { schematic_image?: string }).schematic_image);
</script>

<svelte:head>
	<title>{c.name}{c.based_on ? ` (${c.based_on})` : ''} · {VENDOR_NAMES[c.vendor]} · PCB Schematic Library</title>
	<meta name="description" content="{c.name} by {VENDOR_NAMES[c.vendor]}{c.based_on ? `, based on the ${c.based_on}` : ''}. Parts list, controls, enclosure and where to buy the PCB." />
</svelte:head>

<article class="circuit">
	<header class="plate">
		<div class="face">
			<Faceplate enclosure={c.enclosure} controls={c.controls} size={250} labels title="{c.name} faceplate" />
			<p class="label face-cap">{c.enclosure || 'Enclosure not stated'}{knobs.length ? ` · ${knobs.length} knobs` : ''}</p>
		</div>
		<div class="title">
			<p class="label"><a href="{base}/?vendor={c.vendor}">{VENDOR_NAMES[c.vendor]}</a>{#if c.sku} · <span class="mono">{c.sku}</span>{/if}</p>
			<h1>{c.name}{#if c.subtitle}<span class="sub">{c.subtitle}</span>{/if}</h1>
			{#if c.based_on}
				<p class="based">Based on the <a href="{base}/?based={encodeURIComponent(c.based_on)}">{c.based_on}</a>{#if siblings.length}<span class="dim"> · {siblings.length} other {siblings.length === 1 ? 'board clones' : 'boards clone'} it</span>{/if}</p>
			{/if}
			<dl class="specs">
				<div><dt class="label">Category</dt><dd><a href="{base}/?cat={encodeURIComponent(c.category)}">{c.category}</a>{#if c.effect_type && c.effect_type !== c.category} <span class="dim">· {c.effect_type}</span>{/if}</dd></div>
				{#if knobs.length}<div><dt class="label">Controls</dt><dd>{knobs.join(' · ')}</dd></div>{/if}
				{#if c.difficulty}<div><dt class="label">Difficulty</dt><dd>{c.difficulty}</dd></div>{/if}
				<div><dt class="label">Price</dt><dd class="mono">{currency.format(c.price, c.currency) || 'see vendor'}{#if c.price != null && currency.convert(c.price, c.currency).converted}<span class="dim native">{currency.native(c.price, c.currency)} listed</span>{/if}{#if c.in_stock === false}<span class="warn stock">out of stock</span>{:else if c.in_stock}<span class="dim stock">in stock</span>{/if}</dd></div>
				{#if c.tags.length}<div><dt class="label">Tags</dt><dd>{c.tags.join(', ')}</dd></div>{/if}
			</dl>
			<div class="actions">
				<a class="btn" href={c.url} target="_blank" rel="noopener">{primaryAction(c.vendor)}</a>
				{#if c.doc_url && c.doc_url !== c.url}<a class="btn ghost" href={c.doc_url} target="_blank" rel="noopener">Build document{#if c.doc_version} <span class="mono ver">{c.doc_version}</span>{/if}</a>{/if}
				{#each Object.entries(c.extra_docs) as [label, href]}
					<a class="btn ghost" {href} target="_blank" rel="noopener">{label}</a>
				{/each}
			</div>
		</div>
	</header>

	{#if c.description}
		<section class="desc">
			<h2 class="label strong">From the vendor</h2>
			{#each c.description.split(/\n\s*\n/) as para}
				<p>{para}</p>
			{/each}
		</section>
	{/if}

	<section class="schem">
		<h2 class="label strong">Schematic</h2>
		{#if c.has_kicad}
			<img src="{base}/kicad/{c.file_id}.svg" alt="KiCad schematic of {c.name}" loading="lazy" />
			<p class="small">Redrawn in KiCad. <a href="{base}/kicad/{c.file_id}.kicad_sch" download>Download the .kicad_sch fragment</a> to drop into your own project.</p>
		{:else if schematicImage}
			<img src="{base}/data/{schematicImage}" alt="Schematic page from the {VENDOR_NAMES[c.vendor]} build document" loading="lazy" />
			<p class="dim small">Cached from the vendor build document for local reference. Not for redistribution.</p>
		{:else}
			{#if VENDOR_KIND[c.vendor] === 'blog'}
				<p>The schematic is in the post. <a href={c.url} target="_blank" rel="noopener">Open it at {VENDOR_NAMES[c.vendor]}</a>. No KiCad fragment has been drawn for this circuit yet.</p>
			{:else if VENDOR_KIND[c.vendor] === 'projects'}
				<p>The schematic image is on the project page. <a href={c.url} target="_blank" rel="noopener">Open it at {VENDOR_NAMES[c.vendor]}</a>.</p>
			{:else}
				<p>The schematic is in the vendor's build document{#if c.schematic_page}, page {c.schematic_page}{/if}. <a href={c.doc_url} target="_blank" rel="noopener">Open the build document</a>. No KiCad fragment has been drawn for this circuit yet.</p>
			{/if}
		{/if}
	</section>

	<section class="bom">
		<div class="bom-head">
			<h2 class="label strong">Parts list <span class="mono dim">{c.bom.length} rows</span></h2>
			{#if c.bom.length}<button type="button" class="btn ghost" onclick={copyBom}>{copied ? 'Copied' : 'Copy as TSV'}</button>{/if}
		</div>
		{#if c.bom.length === 0}
			<p class="dim">{#if VENDOR_KIND[c.vendor] === 'projects'}No parts list: the BOM download on this project needs an account at the fab.{:else if VENDOR_KIND[c.vendor] === 'blog'}No parts list could be read from the schematic image; the values are in the picture.{:else}No parts list could be extracted for this board{#if c.vendor === 'guitarpcb'} (GuitarPCB publishes its parts list as an image){/if}. The build document has it.{/if}</p>
		{:else}
			<table class="sheet-table parts">
				<thead><tr><th>Ref</th><th>Value</th><th class="norm">Normalized</th><th>Type</th><th class="notes">Notes</th></tr></thead>
				{#each groups as g}
					<tbody>
						<tr class="group"><th scope="rowgroup" colspan="5">{g.name} <span class="mono dim">{g.rows.length}</span></th></tr>
						{#each g.rows as r}
							<tr>
								<td class="mono ref">{r.ref}</td>
								<td class="mono val">{r.value}</td>
								<td class="mono norm">
									{#if XREF.has(r.category) && r.norm_value}
										<a href="{base}/parts/{partSlug(r)}" title="Every circuit using {r.norm_value}">{r.norm_value}</a>
									{:else}{r.norm_value}{/if}
								</td>
								<td>{r.part_type}</td>
								<td class="notes">{r.notes}</td>
							</tr>
						{/each}
					</tbody>
				{/each}
			</table>
		{/if}
	</section>

	{#if siblings.length}
		<section class="sibs">
			<h2 class="label strong">Other boards based on the {c.based_on}</h2>
			<ul>
				{#each siblings as s}
					<li><Faceplate enclosure={s.enclosure} controls={s.controls} size={26} /> <a href="{base}/circuit/{s.file_id}">{s.name}</a> <span class="dim">{VENDOR_NAMES[s.vendor]}{s.enclosure ? ` · ${s.enclosure}` : ''}{s.price != null ? ` · ${currency.format(s.price, s.currency)}` : ''}</span></li>
				{/each}
			</ul>
		</section>
	{/if}
</article>

<style>
	.circuit { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.plate { display: grid; grid-template-columns: auto 1fr; gap: 32px var(--gutter); align-items: start; padding-bottom: 24px; border-bottom: 1px solid var(--rule-strong); }
	.face { display: flex; flex-direction: column; align-items: center; gap: 10px; }
	.face-cap { text-align: center; }
	.title h1 { font-size: clamp(30px, 4.5vw, 48px); margin: 6px 0 8px; text-wrap: balance; }
	.title h1 .sub { font-weight: 500; color: var(--ink-2); margin-left: 0.3em; }
	.based { font-size: 17px; margin-bottom: 16px; }
	.based a { font-weight: 600; }
	.dim { color: var(--ink-3); }
	.stock { margin-left: 8px; }
	.native { margin-left: 8px; font-size: 12px; }
	.warn { color: var(--warn); font-family: var(--label); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }
	.specs { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, max-content)); gap: 12px 32px; margin: 0 0 20px; }
	.specs div { display: flex; flex-direction: column; gap: 2px; }
	.specs dd { margin: 0; }
	.actions { display: flex; flex-wrap: wrap; gap: 8px; }
	.ver { font-size: 11px; opacity: 0.8; text-transform: none; letter-spacing: 0; }
	section { margin-top: 28px; }
	section h2 { margin-bottom: 10px; }
	.desc p { max-width: 72ch; margin-bottom: 10px; }
	.schem img { border: 1px solid var(--rule); background: white; max-height: 80dvh; width: auto; }
	.small { font-size: 12.5px; margin-top: 6px; }
	.bom-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
	.bom-head h2 { margin: 0; }
	.parts .group th { font-family: var(--label); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; padding: 14px 10px 6px; border-bottom: 1px solid var(--rule-strong); position: static; }
	.parts td.ref { width: 7ch; color: var(--ink-2); }
	.parts td.val { font-weight: 600; }
	.parts td.notes { color: var(--ink-2); }
	.parts .norm a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.sibs ul { list-style: none; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 6px 24px; }
	.sibs li { display: flex; align-items: center; gap: 10px; padding: 4px 0; border-bottom: 1px solid var(--rule); }
	.sibs li a { font-weight: 600; }
	@media (max-width: 760px) {
		.circuit { padding: 16px 16px 40px; }
		.plate { grid-template-columns: 1fr; gap: 16px; }
		.face { flex-direction: row; justify-content: flex-start; gap: 16px; }
		.parts th.norm, .parts td.norm { display: none; }
		.parts th.notes, .parts td.notes { display: none; }
		.parts .norm a { display: none; }
		.bom-head { flex-direction: column; align-items: flex-start; }
	}
</style>
