<script lang="ts">
	import { controlGroup } from '$lib/controls';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import { makerContact, wrongParseUrl } from '$lib/site';
	import Faceplate from '$lib/Faceplate.svelte';
	import { currency } from '$lib/currency.svelte';
	import { bench } from '$lib/bench.svelte';
	import { BUILD_NAMES, PART_CATEGORY_NAMES, PART_ORDER, VENDOR_FAB, VENDOR_NAMES, VENDOR_STORE, VENDOR_KIND, originalsOf, primaryAction, type BomRow } from '$lib/types';

	let { data } = $props();
	const c = $derived(data.circuit);
	const vendorWarning = $derived((data.vendors as Record<string, { warning?: string }> | undefined)?.[c.vendor]?.warning ?? '');
	const siblings = $derived(c.siblings ?? []); // the maker's own board first
	// On a board whose gerbers are free to download, only the other boards the maker sells.
	const free = $derived(!!c.extra_docs['PCB gerbers']);
	const contact = $derived(makerContact(originalsOf(c), c.vendor));
	const makerBoard = $derived(siblings.find((s) => s.own_design));
	const clones = $derived(siblings.filter((s) => !s.own_design).length); // the maker's own board is no clone of itself
	const variants = $derived(c.variants ?? []);
	let variant = $state('');
	$effect(() => {
		variant = variants[0] ?? '';
	});
	const rows = $derived(variants.length ? c.bom.filter((r) => !r.variant || r.variant === variant) : c.bom);
	const groups = $derived.by(() => {
		const m = new Map<string, BomRow[]>();
		for (const r of rows) {
			const k = r.category || 'OTHER';
			if (!m.has(k)) m.set(k, []);
			m.get(k)!.push(r);
		}
		return PART_ORDER.filter((k) => m.has(k)).map((k) => ({ key: k, name: PART_CATEGORY_NAMES[k] ?? k, rows: m.get(k)! }));
	});

	let copied = $state(false);
	async function copyBom() {
		const tsv = ['Ref\tValue\tType\tNotes', ...rows.map((r) => [r.ref, r.value, r.part_type, r.notes].join('\t'))].join('\n');
		await navigator.clipboard.writeText(tsv);
		copied = true;
		setTimeout(() => (copied = false), 1500);
	}
	const knobs = $derived(c.controls.filter((x) => !/^\d+ knobs?$/.test(x)));
	const schematicImage = $derived((c as unknown as { schematic_image?: string }).schematic_image);

	// Where a value came from, from the row's notes: OCR of an image, pairing labels on a schematic, or a
	// hand correction. Text tables and interactive BOMs are exact and carry no marker.
	const SOURCES = [
		{ key: 'ocr', token: /\bOCR\b;?\s*/, label: 'ocr', title: 'Read from an image by OCR: check it against the build document' },
		{ key: 'sch', token: /\bfrom schematic\b;?\s*/, label: 'sch', title: 'Paired from the schematic drawing, not a parts list: check it against the build document' },
		{ key: 'fixed', token: /\bcorrected by hand\b;?\s*/, label: 'fixed', title: 'Corrected by hand: the source had a typo or the reading was wrong' }
	] as const;
	function source(notes: string) {
		let rest = notes || '';
		let found: (typeof SOURCES)[number] | undefined;
		for (const s of SOURCES) {
			if (s.token.test(rest)) {
				found = s.key === 'fixed' || !found ? s : found; // a hand correction outranks how it was first read
				rest = rest.replace(s.token, '');
			}
		}
		return { src: found, rest: rest.replace(/^[;\s]+|[;\s]+$/g, '') };
	}
	const marked = $derived(c.bom.some((r) => source(r.notes).src));
	const lay = $derived(c.layout ?? {});
	const isLayout = $derived(VENDOR_KIND[c.vendor] === 'layout');
</script>

<svelte:head>
	<title>{c.name}{c.original && !c.own_design ? ` (${c.original})` : ''} · {VENDOR_NAMES[c.vendor]} · Akashic</title>
	<meta name="description" content="{c.name} by {VENDOR_NAMES[c.vendor]}{c.original && !c.own_design ? `, based on the ${c.original}` : ''}. Parts list, controls, enclosure and {VENDOR_KIND[c.vendor] === 'layout' ? 'the board layout to build it from' : VENDOR_KIND[c.vendor] === 'kit' ? 'where to buy the kit' : 'where to buy the PCB'}." />
</svelte:head>

<article class="circuit">
	<header class="plate">
		<div class="face">
			<Faceplate enclosure={c.enclosure} controls={c.controls} size={250} labels title="{c.name} faceplate" />
			<p class="label face-cap">{c.enclosure || 'Enclosure not stated'}{knobs.length ? ` · ${knobs.length} ${knobs.length === 1 ? 'knob' : 'knobs'}` : ''}</p>
		</div>
		<div class="title">
			<p class="label"><a href="{base}/?vendor={c.vendor}">{VENDOR_NAMES[c.vendor]}</a>{#if c.sku} · <span class="mono">{c.sku}</span>{/if}</p>
			<h1>{c.name}{#if c.subtitle}<span class="sub">{c.subtitle}</span>{/if}{#if lay.verified === true}<span class="vtag" title="{VENDOR_NAMES[c.vendor]} marks this layout as verified: someone has built it and it works">Verified</span>{/if}</h1>
			{#if c.original}
				<p class="based">{c.own_design ? 'The original ' : 'Based on the '}{#each originalsOf(c) as o, n}{#if n}{' and the '}{/if}<a href="{base}/?based={encodeURIComponent(o)}">{o}</a>{/each}{#if clones}<span class="dim"> · {clones} other {clones === 1 ? (c.own_design ? 'board or layout builds' : 'board clones') : (c.own_design ? 'boards and layouts build' : 'boards clone')} {originalsOf(c).length > 1 ? 'one of them' : 'it'}</span>{/if}{#if makerBoard}<span class="dim"> · the maker's own board is</span>{' '}<a href="{base}/circuit/{makerBoard.file_id}">{makerBoard.name} by {VENDOR_NAMES[makerBoard.vendor]}</a>{/if}</p>
			{:else if c.based_on}
				<p class="based dim">Based on {c.based_on}</p>
			{/if}
			{#if contact?.reach}
				<p class="contact">{contact.reach}: <a href={contact.url} target="_blank" rel="noopener">message {contact.handle ?? contact.maker} on {contact.where}</a>.</p>
			{:else if contact && !free}
				<p class="contact">Want a PCB? {contact.maker} {contact.lead ?? 'designed this circuit and sells boards'}{#if contact.also}, as well as {contact.also}{/if}: <a href={contact.url} target="_blank" rel="noopener">message {contact.handle ?? contact.maker} on {contact.where}</a>.</p>
			{:else if contact?.also}
				<p class="contact">{contact.maker} also sells {contact.also}: <a href={contact.url} target="_blank" rel="noopener">message {contact.handle ?? contact.maker} on {contact.where}</a>.</p>
			{/if}
			<dl class="specs">
				<div><dt class="label">Category</dt><dd><a href="{base}/?cat={encodeURIComponent(c.category)}">{c.category}</a>{#if c.effect_type && c.effect_type !== c.category} <span class="dim">· {c.effect_type}</span>{/if}</dd></div>
				{#if knobs.length}<div><dt class="label">Controls</dt><dd>{#each knobs as k, i}{#if i}{' · '}{/if}{@const g = controlGroup(k)}{#if g}<a href="{base}/?ctl={encodeURIComponent(g.label)}" title="Circuits with a {g.label} control">{k}</a>{:else}{k}{/if}{/each}</dd></div>{/if}
				{#if c.difficulty}<div><dt class="label">Difficulty</dt><dd>{c.difficulty}</dd></div>{/if}
				{#if isLayout}
					<div><dt class="label">Build</dt><dd><a href="{base}/?build={lay.build}">{BUILD_NAMES[lay.build ?? 'vero']}</a>{#if lay.board} <span class="mono">· {lay.board.replace('x', '×')}</span>{/if}{#if lay.cuts != null} <span class="dim">· {lay.cuts} cuts{#if lay.links != null}, {lay.links} links{/if}</span>{/if}</dd></div>
					{#if lay.verified != null}<div><dt class="label">Layout</dt><dd>{#if lay.verified}Verified <span class="dim">· {VENDOR_NAMES[c.vendor]} marks it as built and working</span>{:else}<span class="warn">Unverified</span> <span class="dim">· no build reported at {VENDOR_NAMES[c.vendor]} yet</span>{/if}</dd></div>{/if}
				{:else}
				{#if lay.build}<div><dt class="label">Build</dt><dd><a href="{base}/?build={lay.build}">{BUILD_NAMES[lay.build]}</a>{#if VENDOR_KIND[c.vendor] === 'kit'} <span class="dim">· point to point on terminal strips</span>{/if}</dd></div>{/if}
				<div><dt class="label">Price</dt><dd class="mono">{currency.format(c.price, c.currency) || 'see vendor'}{#if c.price != null && currency.convert(c.price, c.currency).converted}<span class="dim native">{currency.native(c.price, c.currency)} listed</span>{/if}{#if c.delisted}<span class="warn stock">no longer listed</span>{:else if c.in_stock === false}<span class="warn stock">out of stock</span>{:else if c.in_stock}<span class="dim stock">in stock</span>{/if}</dd></div>
					{#if lay.also?.length}<div><dt class="label">Also as</dt><dd>{#each lay.also as a, i}{i ? ' · ' : ''}<a href={a.url} target="_blank" rel="noopener">{BUILD_NAMES[a.build]} layout</a>{/each} <span class="dim">· from {VENDOR_NAMES[c.vendor]}</span></dd></div>{/if}
				{/if}
				{#if c.tags.length}<div><dt class="label">Tags</dt><dd>{c.tags.join(', ')}</dd></div>{/if}
			</dl>
			{#if c.delisted}
				<p class="delisted"><span class="warn">No longer listed</span> {VENDOR_NAMES[c.vendor] ?? c.vendor} stopped listing this board{#if c.last_listed} after {c.last_listed}{/if}. It stays here for reference; the vendor page and build document links may no longer work.</p>
			{/if}
			<div class="actions">
				<a class="btn" href={c.url} target="_blank" rel="noopener">{c.vendor !== 'cryptid' && c.extra_docs['PCB gerbers'] ? 'Get the gerbers' : c.tags?.includes('PCB only') ? `Buy the PCB at ${VENDOR_STORE[c.vendor] ?? VENDOR_NAMES[c.vendor]}` : primaryAction(c.vendor)}</a>
				{#if c.doc_url && c.doc_url !== c.url && VENDOR_KIND[c.vendor] !== 'archive'}<a class="btn ghost" href={c.doc_url} target="_blank" rel="noopener">Build document{#if c.doc_version} <span class="mono ver">{c.doc_version}</span>{/if}</a>{/if}
				{#each Object.entries(c.extra_docs) as [label, href]}
					<a class="btn ghost" {href} target="_blank" rel="noopener">{label}</a>
				{/each}
				{#each lay.also ?? [] as a}
					<a class="btn ghost" href={a.url} target="_blank" rel="noopener">{BUILD_NAMES[a.build]} layout</a>
				{/each}
				{#if bench.ready}<button type="button" class="btn ghost keep" aria-pressed={bench.has(c.id)} onclick={() => bench.toggle(c.id)} title={bench.has(c.id) ? 'Take it off your bench' : 'Keep this circuit on your bench, in this browser'}>{bench.has(c.id) ? 'On my bench ✓' : '+ My bench'}</button>{/if}
			</div>
			{#if bench.has(c.id)}
				<label class="bench-note">
					<span class="label">Bench note</span>
					<input type="text" value={bench.items[c.id]?.note ?? ''} oninput={(e) => bench.setNote(c.id, e.currentTarget.value)} placeholder="Try 2N5088s, order the board in May…" maxlength="300" />
					<a class="label" href="{base}/workbench/bench">My bench</a>
				</label>
			{/if}
			{#if vendorWarning}
				<p class="vendor-warning"><span class="warn">Heads up</span> {vendorWarning}</p>
			{/if}
		</div>
	</header>

	{#if c.description}
		<section class="desc">
			<h2 class="label strong">{isLayout ? 'From the post' : 'From the vendor'}</h2>
			{#each c.description.split(/\n\s*\n/) as para}
				<p>{para}</p>
			{/each}
		</section>
	{/if}

	{#if c.owner_photo}
		<section class="photo">
			<h2 class="label strong">Built</h2>
			<img src={c.owner_photo} alt="The finished {c.name}" loading="lazy" />
		</section>
	{/if}

	<section class="schem">
		<h2 class="label strong">Schematic</h2>
		{#if c.owner_schematic}
			<img src="{base}/data/{c.owner_schematic}" alt="Schematic of {c.name}" loading="lazy" />
			<p class="small">Drawn by {VENDOR_NAMES[c.vendor]}, <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener">CC BY-NC-SA 4.0</a>. <a href={c.url} target="_blank" rel="noopener">Gerbers{c.tags?.includes('faceplate') ? ' and faceplate' : ''} on GitHub</a>.</p>
		{:else if c.has_kicad}
			<img src="{base}/kicad/{c.file_id}.svg" alt="KiCad schematic of {c.name}" loading="lazy" />
			<p class="small">Redrawn in KiCad. <a href="{base}/kicad/{c.file_id}.kicad_sch" download>Download the .kicad_sch fragment</a> to drop into your own project.</p>
		{:else if schematicImage}
			<img src="{base}/data/{schematicImage}" alt="Schematic page from the {VENDOR_NAMES[c.vendor]} build document" loading="lazy" />
			<p class="dim small">Cached from the vendor build document for local reference. Not for redistribution.</p>
		{:else}
			{#if isLayout}
				<p>This is a board layout, a drawing of where each part goes, and the post may link the schematic it was drawn from. <a href={c.url} target="_blank" rel="noopener">Open the layout at {VENDOR_NAMES[c.vendor]}</a>. No KiCad fragment has been drawn for this circuit yet.</p>
			{:else if VENDOR_KIND[c.vendor] === 'archive'}
				<p>The schematic is the archived file. <a href={c.url} target="_blank" rel="noopener">Open it at {VENDOR_NAMES[c.vendor]}</a>, or <a href={c.doc_url} target="_blank" rel="noopener">browse its folder</a>.</p>
			{:else if VENDOR_KIND[c.vendor] === 'blog'}
				<p>The schematic is in the post. <a href={c.url} target="_blank" rel="noopener">Open it at {VENDOR_NAMES[c.vendor]}</a>. No KiCad fragment has been drawn for this circuit yet.</p>
			{:else if VENDOR_KIND[c.vendor] === 'projects' && c.extra_docs['Eagle board file']}
				<p>No schematic is shared with this board: the parts list was read from its <a href={c.extra_docs['Eagle board file']} target="_blank" rel="noopener">Eagle board file</a>. <a href={c.url} target="_blank" rel="noopener">Open the project at {VENDOR_FAB[c.vendor] ?? VENDOR_NAMES[c.vendor]}</a>.</p>
			{:else if VENDOR_KIND[c.vendor] === 'projects' && c.vendor !== 'pcbway-gtu'}
				<p>No schematic or board file is shared with this board. <a href={c.url} target="_blank" rel="noopener">Open the project at {VENDOR_FAB[c.vendor] ?? VENDOR_NAMES[c.vendor]}</a>.</p>
			{:else if VENDOR_KIND[c.vendor] === 'projects'}
				<p>The schematic image is on the project page. <a href={c.url} target="_blank" rel="noopener">Open it at {VENDOR_FAB[c.vendor] ?? VENDOR_NAMES[c.vendor]}</a>.</p>
			{:else}
				<p>The schematic is in the vendor's build document{#if c.schematic_page}, page {c.schematic_page}{/if}. <a href={c.doc_url} target="_blank" rel="noopener">Open the build document</a>. No KiCad fragment has been drawn for this circuit yet.</p>
			{/if}
		{/if}
	</section>

	<section class="bom">
		<div class="bom-head">
			<h2 class="label strong">Parts list <span class="mono dim">{rows.length} rows</span></h2>
			{#if c.bom.length}<button type="button" class="btn ghost" onclick={copyBom}>{copied ? 'Copied' : 'Copy as TSV'}</button>{/if}
			<a class="btn ghost report-link" href={wrongParseUrl(c.name, page.url.href)} target="_blank" rel="noopener" title="Open a GitHub issue with this circuit filled in">Report a wrong parse</a>
		</div>
		{#if c.bom.length}<p class="hint">Got parts in a drawer? <a href="{base}/workbench/build">See what you can build with them</a>.</p>{/if}
		{#if variants.length > 1}
			<div class="variants" role="group" aria-label="Build variant">
				<span class="label">Variant</span>
				{#each variants as v}
					<button type="button" class="btn ghost" class:on={v === variant} aria-pressed={v === variant} onclick={() => (variant = v)}>{v}</button>
				{/each}
			</div>
		{/if}
		{#if isLayout && c.bom.length && c.bom.every((r) => /layout legend/.test(r.notes))}
			<p class="dim legend-note">Only the parts the layout names in its legend are listed: the active parts and the pots. The resistor and capacitor values are printed on the parts in the drawing.</p>
		{/if}
		{#if c.bom.length === 0}
			<p class="dim">{#if isLayout}No parts could be read from this layout; the values are printed on the parts in the drawing.{:else if VENDOR_KIND[c.vendor] === 'projects' && c.vendor !== 'pcbway-gtu'}No parts list: the designer shared only the board, with no schematic, BOM or board file.{:else if VENDOR_KIND[c.vendor] === 'projects'}No parts list: the BOM download on this project needs an account at the fab.{:else if VENDOR_KIND[c.vendor] === 'blog' || VENDOR_KIND[c.vendor] === 'archive'}No parts list could be read from the schematic image; the values are in the picture.{:else}No parts list could be extracted for this board{#if c.vendor === 'guitarpcb'} (GuitarPCB publishes its parts list as an image){/if}. The build document has it.{/if}</p>
		{:else}
			{#if marked}
				<p class="src-legend dim"><span class="src">ocr</span> read from an image · <span class="src">sch</span> paired from the schematic · <span class="src fixed">fixed</span> corrected by hand. Check marked values against the build document.</p>
			{/if}
			{#if c.uncertain?.length}
				<details class="unsure" open={c.uncertain.length <= 4}>
					<summary><span class="warn">Check before you build</span> <span class="dim">· {c.uncertain.length} {c.uncertain.length === 1 ? 'value' : 'values'} the reader of this {isLayout ? 'layout' : 'schematic'} was not sure of</span></summary>
					<ul>{#each c.uncertain as u}<li>{u}</li>{/each}</ul>
				</details>
			{/if}
			<table class="sheet-table parts">
				<thead><tr><th>Ref</th><th>Value</th><th class="norm">Normalized</th><th>Type</th><th class="notes">Notes</th></tr></thead>
				{#each groups as g}
					<tbody>
						<tr class="group"><th scope="rowgroup" colspan="5">{g.name} <span class="mono dim">{g.rows.length}</span></th></tr>
						{#each g.rows as r}
							{@const s = source(r.notes)}
							<tr>
								<td class="mono ref">{r.ref}</td>
								<td class="mono val">{r.value}{#if s.src}<span class="src" class:fixed={s.src.key === 'fixed'} title={s.src.title}>{s.src.label}</span>{/if}</td>
								<td class="mono norm">
									{#if r.xref?.length === 1}
										<a href="{base}/parts/{r.xref[0][1]}" title="Every circuit using {r.xref[0][0]}">{r.norm_value || r.xref[0][0]}</a>
									{:else if r.xref?.length}
										{#each r.xref as [part, slug], i}{i ? ' / ' : ''}<a href="{base}/parts/{slug}" title="Every circuit using {part}">{part}</a>{/each}
									{:else}{r.norm_value}{/if}
								</td>
								<td>{r.part_type}</td>
								<td class="notes">{s.rest}</td>
							</tr>
						{/each}
					</tbody>
				{/each}
			</table>
		{/if}
	</section>

	{#if siblings.length}
		<section class="sibs">
			<h2 class="label strong">Other boards based on the {originalsOf(c).join(' or the ')}</h2>
			<ul>
				{#each siblings as s}
					<li><Faceplate enclosure={s.enclosure} controls={s.controls} size={26} /> <a href="{base}/circuit/{s.file_id}">{s.name}</a> <span class="dim">{s.own_design ? 'the original · ' : ''}{VENDOR_NAMES[s.vendor]}{s.enclosure ? ` · ${s.enclosure}` : ''}{s.price != null ? ` · ${currency.format(s.price, s.currency)}` : ''}</span></li>
				{/each}
			</ul>
		</section>
	{/if}
</article>

<style>
	.vtag { display: inline-block; vertical-align: middle; margin-left: 12px; font-family: var(--label); font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase; font-weight: 400; color: var(--coat); border: 1px solid var(--coat); border-radius: 3px; padding: 1px 6px; }
	.circuit { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.plate { display: grid; grid-template-columns: auto 1fr; gap: 32px var(--gutter); align-items: start; padding-bottom: 24px; border-bottom: 1px solid var(--rule-strong); }
	.face { display: flex; flex-direction: column; align-items: center; gap: 10px; }
	.face-cap { text-align: center; }
	.title h1 { font-size: clamp(30px, 4.5vw, 48px); margin: 6px 0 8px; text-wrap: balance; }
	.title h1 .sub { font-weight: 500; color: var(--ink-2); margin-left: 0.3em; }
	.based { font-size: 17px; margin-bottom: 16px; }
	.based a { font-weight: 600; }
	.contact { margin: -8px 0 16px; color: var(--ink-2); }
	.contact a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.dim { color: var(--ink-3); }
	.stock { margin-left: 8px; }
	.delisted { margin: 12px 0 0; padding: 8px 12px; border: 1px solid var(--rule-strong); border-radius: var(--radius); color: var(--ink-2); max-width: 70ch; }
	.delisted .warn { margin-right: 6px; }
	.native { margin-left: 8px; font-size: 12px; }
	.warn { color: var(--warn); font-family: var(--label); text-transform: uppercase; letter-spacing: 0.08em; font-size: 12px; }
	.specs { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, max-content)); gap: 12px 32px; margin: 0 0 20px; }
	.specs div { display: flex; flex-direction: column; gap: 2px; }
	.specs dd { margin: 0; }
	.actions { display: flex; flex-wrap: wrap; gap: 8px; }
	.keep[aria-pressed='true'] { border-color: var(--coat); color: var(--coat); }
	.bench-note { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; margin-top: 10px; max-width: 640px; }
	.bench-note input { flex: 1; min-width: 200px; height: 34px; padding: 0 10px; border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet-2); color: var(--ink); font: inherit; font-size: 14px; }
	.bench-note input:focus { outline: none; border-color: var(--coat); box-shadow: 0 0 0 3px var(--coat-tint); background: var(--sheet); }
	.bench-note a { color: var(--ink-2); text-decoration: underline; text-underline-offset: 3px; }
	.variants { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin: 0 0 12px; }
	.variants .label { margin-right: 4px; }
	.variants .btn.on { background: var(--coat); color: var(--coat-ink); border-color: var(--coat); }
	.vendor-warning { margin: 10px 0 0; max-width: 62ch; font-size: 14px; line-height: 1.45; color: var(--ink-2); }
	.vendor-warning .warn { margin-right: 6px; }
	.ver { font-size: 11px; opacity: 0.8; text-transform: none; letter-spacing: 0; }
	section { margin-top: 28px; }
	section h2 { margin-bottom: 10px; }
	.desc p { max-width: 72ch; margin-bottom: 10px; }
	.photo img { border: 1px solid var(--rule); max-height: 60dvh; width: auto; max-width: 100%; }
	.schem img { border: 1px solid var(--rule); background: white; max-height: 80dvh; width: auto; }
	.small { font-size: 12.5px; margin-top: 6px; }
	.bom-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 8px; }
	.bom-head h2 { margin: 0; }
	.hint { margin: 0 0 10px; font-size: 14px; color: var(--ink-3); }
	.hint a { color: var(--ink-2); text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.hint a:hover { color: var(--ink); text-decoration-color: var(--coat); }
	.parts .group th { font-family: var(--label); font-size: 13px; letter-spacing: 0.1em; text-transform: uppercase; padding: 14px 10px 6px; border-bottom: 1px solid var(--rule-strong); position: static; }
	.parts td.ref { width: 7ch; color: var(--ink-2); }
	.parts td.val { font-weight: 600; }
	.parts td.notes { color: var(--ink-2); }
	.src { margin-left: 6px; padding: 0 4px; border: 1px solid var(--rule-strong); border-radius: 3px; font-family: var(--label); font-weight: 600; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); vertical-align: 1px; cursor: help; }
	.src.fixed { border-color: var(--coat); color: var(--coat); }
	.src-legend { font-size: 12.5px; margin: 0 0 8px; }
	.unsure { margin: 0 0 12px; padding: 8px 12px; border: 1px solid var(--rule-strong); border-left: 3px solid var(--warn); border-radius: var(--radius); }
	.unsure summary { cursor: pointer; }
	.unsure ul { margin: 8px 0 2px; padding-left: 18px; max-width: 90ch; }
	.unsure li { margin-bottom: 4px; color: var(--ink-2); font-size: 14px; }
	.src-legend .src { margin-left: 0; cursor: default; }
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
