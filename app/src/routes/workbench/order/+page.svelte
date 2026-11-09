<script lang="ts">
	import { browser } from '$app/env';
	import { bench } from '#lib/bench.svelte.ts';
	import { currency } from '#lib/currency.svelte.ts';
	import { loadCircuit } from '#lib/data.ts';
	import { BUILD_NAMES, PART_CATEGORY_NAMES, PART_ORDER, VENDOR_KIND, VENDOR_NAMES, type BomRow, type Circuit, type IndexEntry } from '#lib/types.ts';

	let { data } = $props();
	const byId = $derived(new Map(data.index.map((e) => [e.id, e])));
	const entries = $derived(bench.ids.map((id) => byId.get(id)).filter((e): e is IndexEntry => !!e));
	const countOf = (id: string) => bench.items[id]?.count ?? 1;

	// Each circuit's full record, for its parts list: fetched once per visit, from the bundle it is in.
	let records = $state<Record<string, Circuit | 'failed'>>({});
	const pending = new Set<string>();
	$effect(() => {
		if (!browser) return;
		for (const e of entries) {
			if (e.id in records || pending.has(e.id)) continue;
			pending.add(e.id);
			loadCircuit(e.file_id)
				.then((c) => (records[e.id] = c))
				.catch(() => (records[e.id] = 'failed'))
				.finally(() => pending.delete(e.id));
		}
	});
	const loading = $derived(entries.some((e) => !(e.id in records)));

	const variantsOf = (c: Circuit | undefined) => c?.variants ?? [];
	function variantOf(id: string, c: Circuit): string {
		const vs = variantsOf(c);
		const v = bench.items[id]?.variant ?? '';
		return vs.includes(v) ? v : (vs[0] ?? '');
	}
	function rowsOf(id: string, c: Circuit): BomRow[] {
		const v = variantOf(id, c);
		return variantsOf(c).length ? c.bom.filter((r) => !r.variant || r.variant === v) : c.bom;
	}
	/** A row stands for one part, or for several when a shopping list names it by quantity ('×3'). */
	const qtyOf = (r: BomRow) => (/^×(\d+)$/.exec(r.ref.trim()) ? parseInt(r.ref.trim().slice(1), 10) : 1);
	/** Electrolytic and tantalum capacitors are bought apart from film and ceramic ones of the same value. */
	function capKind(r: BomRow): string {
		const t = `${r.part_type} ${r.notes} ${r.value}`;
		if (/tantal/i.test(t)) return 'tantalum';
		if (/electrolytic|\belec\b|\be-?cap\b|alumin(?:um|ium)/i.test(t)) return 'electrolytic';
		if (/film|ceramic|mlcc|c0g|np0|box|poly|mylar|wima|mica|bipolar|non-?polar/i.test(t)) return '';
		// A list that names no type: 4.7µ and up is an electrolytic in a pedal.
		const m = /^(\d+(?:\.\d+)?)\s*([pnuµm])?/i.exec(r.norm_value || r.value);
		const scale: Record<string, number> = { p: 1e-12, n: 1e-9, u: 1e-6, µ: 1e-6, m: 1e-3 };
		return m && m[2] && parseFloat(m[1]) * scale[m[2].toLowerCase()] >= 4.7e-6 ? 'electrolytic' : '';
	}

	// The parts list from What can I build, to leave out what is already in the drawers.
	let inv = $state<Record<string, number | null>>({});
	let assume = $state<string[]>([]);
	$effect(() => {
		try {
			const v = JSON.parse(localStorage.getItem('akashic-inventory') ?? 'null');
			if (v && typeof v.parts === 'object') inv = Object.fromEntries(Object.entries(v.parts).filter(([, n]) => n === null || typeof n === 'number')) as Record<string, number | null>;
			if (v && Array.isArray(v.assume)) assume = v.assume.filter((c: unknown) => typeof c === 'string');
		} catch {
			// storage blocked or empty: nothing on hand
		}
	});
	const keyOfSlug = $derived(new Map(data.parts.map((p) => [p.slug, p.key])));
	const hasInventory = $derived(Object.keys(inv).length > 0 || assume.length > 0);
	let leaveOut = $state(true);

	type Line = { cat: string; value: string; kind: string; qty: number; have: number; types: Map<string, number>; used: Map<string, number>; slug: string; sort: number };
	const lines = $derived.by(() => {
		const m = new Map<string, Line>();
		for (const e of entries) {
			const c = records[e.id];
			const n = countOf(e.id);
			if (!c || c === 'failed' || !n) continue;
			for (const r of rowsOf(e.id, c)) {
				const cat = r.category || 'OTHER';
				const value = (r.norm_value || r.value).trim();
				if (!value) continue;
				const kind = cat === 'C' ? capKind(r) : '';
				const key = `${cat}|${value.toUpperCase()}|${kind}`;
				let l = m.get(key);
				if (!l) m.set(key, (l = { cat, value, kind, qty: 0, have: 0, types: new Map(), used: new Map(), slug: r.xref?.[0]?.[1] ?? '', sort: r.sort_key ?? 0 }));
				const q = qtyOf(r) * n;
				l.qty += q;
				const t = r.part_type.trim();
				if (t) l.types.set(t, (l.types.get(t) ?? 0) + q);
				l.used.set(e.name, (l.used.get(e.name) ?? 0) + q);
			}
		}
		for (const l of m.values()) {
			if (assume.includes(l.cat)) l.have = l.qty;
			else {
				const k = l.slug ? keyOfSlug.get(l.slug) : undefined;
				if (k && k in inv) l.have = inv[k] ?? l.qty; // no number on the list: enough for any order
			}
		}
		return [...m.values()];
	});
	const toOrder = (l: Line) => (leaveOut ? Math.max(0, l.qty - l.have) : l.qty);
	const groups = $derived.by(() => {
		const out: { cat: string; lines: Line[]; total: number }[] = [];
		const cats = [...PART_ORDER, ...new Set(lines.map((l) => l.cat).filter((c) => !PART_ORDER.includes(c)))];
		for (const cat of cats) {
			const ls = lines.filter((l) => l.cat === cat && toOrder(l) > 0).sort((a, b) => a.kind.localeCompare(b.kind) || a.sort - b.sort || a.value.localeCompare(b.value));
			if (ls.length) out.push({ cat, lines: ls, total: ls.reduce((s, l) => s + toOrder(l), 0) });
		}
		return out;
	});
	const onHand = $derived(leaveOut ? lines.filter((l) => l.have > 0) : []);
	const covered = $derived(onHand.filter((l) => toOrder(l) === 0).length);

	const typeText = (l: Line) => {
		const ts = [...l.types.entries()].sort((a, b) => b[1] - a[1]).map(([t]) => t);
		return ts.length > 2 ? `${ts.slice(0, 2).join('; ')}; …` : ts.join('; ');
	};
	const usedText = (l: Line) => [...l.used.entries()].map(([name, q]) => (q > 1 ? `${name} ×${q}` : name)).join(', ');
	const label = (l: Line) => (l.kind ? `${l.value} ${l.kind}` : l.value);

	// What to get for each circuit besides its parts: the board, kit or drawing, and the enclosure.
	function source(e: IndexEntry): string {
		const kind = VENDOR_KIND[e.vendor] ?? 'shop';
		if (kind === 'layout') return `${BUILD_NAMES[e.builds?.[0] ?? 'vero']}${e.board ? ` ${e.board.replace('x', '×')}` : ''}`;
		return { shop: 'PCB', kit: 'Kit', projects: 'PCB from a fab', repo: 'Gerbers, from a fab', blog: 'From the post', archive: 'From the schematic' }[kind];
	}
	const ordered = $derived(entries.filter((e) => countOf(e.id) > 0));
	const boardTotal = $derived.by(() => {
		let sum = 0;
		let cur = '';
		for (const e of ordered) {
			if (e.price == null || (VENDOR_KIND[e.vendor] ?? 'shop') === 'layout') continue;
			const c = currency.convert(e.price, e.currency);
			if (cur && c.currency !== cur) return '';
			cur = c.currency;
			sum += c.amount * countOf(e.id);
		}
		return cur ? currency.format(sum, cur) : '';
	});
	const enclosures = $derived.by(() => {
		const m = new Map<string, number>();
		for (const e of ordered) if (e.enclosure) m.set(e.enclosure, (m.get(e.enclosure) ?? 0) + countOf(e.id));
		return [...m.entries()].sort((a, b) => a[0].localeCompare(b[0]));
	});
	const noParts = $derived(ordered.filter((e) => {
		const c = records[e.id];
		return c === 'failed' || (c && !rowsOf(e.id, c).length);
	}));

	// Out of the page: a CSV for a spreadsheet, or plain text for a note or a message to a parts shop.
	const csvCell = (s: string | number) => (/[",\n]/.test(String(s)) ? `"${String(s).replace(/"/g, '""')}"` : String(s));
	function csv(): string {
		const out = [['Category', 'Value', 'Quantity', 'Type', 'Used in'].join(',')];
		for (const g of groups) for (const l of g.lines) out.push([PART_CATEGORY_NAMES[l.cat] ?? l.cat, label(l), toOrder(l), typeText(l), usedText(l)].map(csvCell).join(','));
		for (const [box, n] of enclosures) out.push(['Enclosures', box, n, '', ''].map(csvCell).join(','));
		return out.join('\n') + '\n';
	}
	function text(): string {
		const out: string[] = [];
		for (const g of groups) {
			out.push(PART_CATEGORY_NAMES[g.cat] ?? g.cat);
			for (const l of g.lines) out.push(`  ${toOrder(l)} × ${label(l)}`);
		}
		if (enclosures.length) out.push('Enclosures', ...enclosures.map(([box, n]) => `  ${n} × ${box}`));
		return out.join('\n') + '\n';
	}
	let status = $state('');
	const say = (msg: string) => {
		status = msg;
		setTimeout(() => status === msg && (status = ''), 4000);
	};
	function download() {
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([csv()], { type: 'text/csv' }));
		a.download = `akashic-order-${new Date().toISOString().slice(0, 10)}.csv`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(a.href), 1000);
	}
	async function copy() {
		try {
			await navigator.clipboard.writeText(text());
			say('Order list copied.');
		} catch {
			say('The browser would not copy the list.');
		}
	}
</script>

<svelte:head>
	<title>Order list · Akashic</title>
	<meta name="description" content="Every part the circuits on your bench need, added up: resistors, capacitors, semiconductors, pots, switches and jacks, ready to order." />
</svelte:head>

<h1>Order list</h1>
<p class="lede">Every part the circuits on <a href="/workbench/bench">My bench</a> need, added up across them: resistors, capacitors, semiconductors, pots, switches, jacks and the rest of each parts list. Set how many of each circuit you are building and which variant. The list comes from the parts lists as Akashic read them, so check it against each build document before you order.</p>

{#if !bench.ready}
	<p class="dim">Reading your bench…</p>
{:else if !entries.length}
	<div class="empty">
		<p class="label strong">Nothing on the bench yet</p>
		<p>Press <span class="mono">+ My bench</span> on the page of each circuit you want to build. Their parts add up here.</p>
	</div>
{:else}
	<section>
		<h2 class="label strong">Circuits <span class="mono dim">{ordered.length}</span></h2>
		<table class="sheet-table boards">
			<thead><tr><th>Circuit</th><th class="n">Build</th><th>Variant</th><th>Get</th><th class="n price">Price</th><th class="encl">Enclosure</th></tr></thead>
			<tbody>
				{#each entries as e (e.id)}
					{@const c = records[e.id]}
					{@const vs = c && c !== 'failed' ? variantsOf(c) : []}
					<tr class:off={!countOf(e.id)}>
						<td><a class="name" href="/circuit/{e.file_id}">{e.name}</a> <span class="dim src">{VENDOR_NAMES[e.vendor]}</span></td>
						<td class="n"><input class="count mono" type="number" min="0" max="99" value={countOf(e.id)} oninput={(ev) => bench.setCount(e.id, parseInt(ev.currentTarget.value, 10) || 0)} aria-label="How many {e.name} to build" /></td>
						<td>
							{#if vs.length > 1 && c && c !== 'failed'}
								<select value={variantOf(e.id, c)} onchange={(ev) => bench.setVariant(e.id, ev.currentTarget.value)} aria-label="Variant of {e.name}">
									{#each vs as v}<option value={v}>{v}</option>{/each}
								</select>
							{:else}<span class="dim">—</span>{/if}
						</td>
						<td><a href={e.url} target="_blank" rel="noopener">{source(e)}</a></td>
						<td class="n mono price">{(VENDOR_KIND[e.vendor] ?? 'shop') !== 'layout' ? currency.format(e.price, e.currency) || '—' : '—'}</td>
						<td class="encl dim">{e.enclosure || '—'}</td>
					</tr>
				{/each}
			</tbody>
			{#if boardTotal}<tfoot><tr><td colspan="4" class="dim">Boards and kits</td><td class="n mono price">{boardTotal}</td><td class="encl"></td></tr></tfoot>{/if}
		</table>
		<p class="note dim">Set a count to 0 to keep a circuit on the bench but out of the order.</p>
		{#if noParts.length}
			<p class="warn-note">No parts list for {noParts.map((e) => e.name).join(', ')}: get {noParts.length === 1 ? 'its parts' : 'their parts'} from the build document.</p>
		{/if}
	</section>

	<section>
		<h2 class="label strong">Parts</h2>
		<div class="tools">
			{#if hasInventory}
				<label class="chip-check"><input type="checkbox" bind:checked={leaveOut} /> Leave out what I have in <a href="/workbench/build">What can I build</a></label>
			{/if}
			<button type="button" class="btn ghost" onclick={download} disabled={!groups.length}>Download CSV</button>
			<button type="button" class="btn ghost" onclick={copy} disabled={!groups.length}>Copy as text</button>
		</div>
		<p class="status" aria-live="polite">{status}</p>
		{#if loading}<p class="dim">Reading the parts lists…</p>{/if}
		{#if onHand.length}<p class="note dim">{covered} {covered === 1 ? 'line is' : 'lines are'} covered by your parts and left out{onHand.length > covered ? `; ${onHand.length - covered} more ${onHand.length - covered === 1 ? 'is' : 'are'} cut to what you are short` : ''}.</p>{/if}
		{#each groups as g (g.cat)}
			<h3 class="label">{PART_CATEGORY_NAMES[g.cat] ?? g.cat} <span class="mono dim">{g.total}</span></h3>
			<table class="sheet-table parts">
				<thead><tr><th class="n">Qty</th><th>Value</th><th class="type">Type</th><th>Used in</th></tr></thead>
				<tbody>
					{#each g.lines as l (l.value + l.kind)}
						<tr>
							<td class="n mono">{toOrder(l)}</td>
							<td class="mono val">{#if l.slug}<a href="/parts/{l.slug}">{l.value}</a>{:else}{l.value}{/if}{#if l.kind}<span class="dim kind">{l.kind}</span>{/if}</td>
							<td class="type dim">{typeText(l)}</td>
							<td class="used dim">{usedText(l)}</td>
						</tr>
					{/each}
				</tbody>
			</table>
		{/each}
		{#if enclosures.length}
			<h3 class="label">Enclosures <span class="mono dim">{enclosures.reduce((s, [, n]) => s + n, 0)}</span></h3>
			<table class="sheet-table parts">
				<thead><tr><th class="n">Qty</th><th>Size</th></tr></thead>
				<tbody>
					{#each enclosures as [box, n]}<tr><td class="n mono">{n}</td><td class="mono">{box}</td></tr>{/each}
				</tbody>
			</table>
		{/if}
		{#if !loading && !groups.length && !enclosures.length}<p class="dim">Nothing to order.</p>{/if}
	</section>
{/if}

<style>
	.dim { color: var(--ink-3); }
	.name { font-weight: 600; }
	.src { font-size: 13px; }
	.lede a, .chip-check a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.boards td a:not(.name) { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.boards tr.off td { opacity: 0.5; }
	.boards tfoot td { border-top: 1px solid var(--rule-strong); padding-top: 6px; }
	.count { width: 4.5em; height: 30px; padding: 0 6px; border: 1px solid var(--rule); border-radius: var(--radius); background: var(--sheet); color: var(--ink); text-align: right; }
	select { height: 30px; max-width: 16em; border: 1px solid var(--rule); border-radius: var(--radius); background: var(--sheet); color: var(--ink); font: inherit; font-size: 14px; }
	.tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 12px; }
	.tools .btn { padding: 6px 12px; font-size: 13px; }
	.chip-check { display: inline-flex; align-items: center; gap: 6px; font-size: 14px; color: var(--ink-2); margin-right: 8px; }
	.status { min-height: 1.4em; margin: 6px 0 4px; color: var(--ink-2); font-size: 14px; }
	.note { font-size: 14px; margin: 6px 0 0; }
	.warn-note { color: var(--warn); font-size: 14px; margin: 6px 0 0; }
	h3 .mono { font-size: 13px; margin-left: 4px; }
	/* Fixed columns, so the tables of each kind of part line up under one another. */
	.parts { margin-bottom: 8px; width: 100%; table-layout: fixed; }
	.parts th:nth-child(2) { width: 13em; }
	.parts td { overflow-wrap: anywhere; }
	.parts .n { width: 4em; }
	.parts .kind { margin-left: 0.5em; font-family: var(--body); }
	.parts .val a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.parts .type { width: 30%; }
	.used { font-size: 13px; }
	.empty { border: 1px dashed var(--rule-strong); border-radius: var(--radius); padding: 20px 22px; max-width: 62ch; margin-top: 8px; }
	.empty p { margin: 0 0 6px; color: var(--ink-2); }
	@media (max-width: 860px) { .encl, .type { display: none; } }
	@media (max-width: 560px) { .price, .src { display: none; } }
</style>
