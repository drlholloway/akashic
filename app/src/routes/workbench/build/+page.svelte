<script lang="ts">
	import { base } from '$app/paths';
	import { PART_CATEGORY_NAMES, PART_ORDER, VENDOR_NAMES, type IndexEntry, type PartEntry } from '$lib/types';

	let { data } = $props();

	// The parts on hand, by catalog key ('IC:TL072'), each with how many (null: plenty), and the
	// categories taken as always on hand. Kept in this browser only.
	const STORE = 'akashic-inventory';
	let inv = $state<Record<string, number | null>>({});
	let assume = $state<string[]>(['SW']);
	let loaded = $state(false);
	$effect(() => {
		try {
			const v = JSON.parse(localStorage.getItem(STORE) ?? 'null');
			if (v && typeof v.parts === 'object') inv = Object.fromEntries(Object.entries(v.parts).filter(([, n]) => n === null || typeof n === 'number')) as Record<string, number | null>;
			if (v && Array.isArray(v.assume)) assume = v.assume.filter((c: unknown) => typeof c === 'string');
		} catch {
			// storage blocked or empty: start with nothing
		}
		loaded = true;
	});
	$effect(() => {
		const out = JSON.stringify({ parts: inv, assume });
		if (!loaded) return;
		try {
			localStorage.setItem(STORE, out);
		} catch {
			// the page still works; it just forgets on reload
		}
	});

	const at = $derived(new Map(data.parts.map((p, i) => [p.key, i])));
	const byId = $derived(new Map(data.index.map((e) => [e.id, e])));
	const categories = $derived(PART_ORDER.filter((c) => data.parts.some((p) => p.category === c)));
	const owned = $derived(Object.keys(inv).filter((k) => at.has(k)));
	const add = (key: string) => {
		if (!(key in inv)) inv[key] = null;
	};
	const remove = (key: string) => {
		delete inv[key];
	};
	const setQty = (key: string, v: string) => {
		const n = parseInt(v, 10);
		inv[key] = Number.isFinite(n) && n > 0 ? n : null;
	};

	// The picker: the catalog, most used first, narrowed by category and by what is typed.
	let q = $state('');
	let cat = $state('');
	const suggestions = $derived.by(() => {
		const t = q.trim().toLowerCase();
		const pool = data.parts.filter((p) => !(p.key in inv) && (cat ? p.category === cat : !assume.includes(p.category)));
		if (!t) return pool.slice(0, 8);
		const starts = pool.filter((p) => p.value.toLowerCase().startsWith(t));
		const rest = pool.filter((p) => !p.value.toLowerCase().startsWith(t) && (p.value.toLowerCase().includes(t) || (p.desc ?? '').toLowerCase().includes(t)));
		return [...starts, ...rest].slice(0, 12);
	});
	// Enter adds the first match; a pasted list ('TL072, 2N5088, B100k') adds every part it names.
	let skipped = $state<string[]>([]);
	function submit(ev: SubmitEvent) {
		ev.preventDefault();
		const tokens = q.split(/[,;\n]+/).map((t) => t.trim()).filter(Boolean);
		skipped = [];
		if (tokens.length > 1) {
			for (const t of tokens) {
				const hit = data.parts.find((p) => p.value.toLowerCase() === t.toLowerCase() && (!cat || p.category === cat));
				if (hit) add(hit.key);
				else skipped.push(t);
			}
		} else if (suggestions[0]) add(suggestions[0].key);
		else return;
		q = '';
	}

	// What the parts on hand cover: each part itself and what it stands in for (a 1N4739 is a 9V1 zener,
	// a BC549C is a BC549 and a BC549 will do for a BC549C).
	const cover = $derived.by(() => {
		const m = new Map<number, number>();
		for (const k of owned) {
			const i = at.get(k)!;
			const n = inv[k] ?? Infinity;
			for (const j of [i, ...(data.needs.also[i] ?? [])]) m.set(j, (m.get(j) ?? 0) + n);
		}
		return m;
	});

	type Gap = { n: number; have: number; alts: PartEntry[] };
	type Row = { e: IndexEntry; total: number; gaps: Gap[]; unread: number };
	const MAX_AWAY = 3;
	const rows = $derived.by(() => {
		const out: Row[] = [];
		if (!owned.length) return out;
		const skip = new Set(assume);
		for (const [id, need] of Object.entries(data.needs.circuits)) {
			const e = byId.get(id);
			if (!e) continue;
			let total = 0;
			const gaps: Gap[] = [];
			for (const [n, ...alts] of need.n) {
				if (skip.has(data.parts[alts[0]].category)) continue;
				total++;
				if (gaps.length > MAX_AWAY) continue;
				let have = 0;
				for (const a of alts) have += cover.get(a) ?? 0;
				if (have < n) gaps.push({ n, have, alts: alts.map((a) => data.parts[a]) });
			}
			// Close means some of it is on hand: a board that has none of its parts is not 'two away', however small.
			if (gaps.length <= MAX_AWAY && gaps.length < total) out.push({ e, total, gaps, unread: need.u ?? 0 });
		}
		// The boards that use the most of what is on hand come first: a one-diode utility board matches nearly any list.
		return out.sort((a, b) => a.gaps.length - b.gaps.length || b.total - a.total || a.e.name.localeCompare(b.e.name));
	});
	const counts = $derived([0, 1, 2, 3].map((n) => rows.filter((r) => r.gaps.length === n).length));

	// The parts that would finish the most boards: the one missing part of every board that is one away.
	const nextBuys = $derived.by(() => {
		const m = new Map<string, { p: PartEntry; boards: number }>();
		for (const r of rows) {
			if (r.gaps.length !== 1) continue;
			for (const p of r.gaps[0].alts) {
				const g = m.get(p.key) ?? { p, boards: 0 };
				g.boards++;
				m.set(p.key, g);
			}
		}
		return [...m.values()].sort((a, b) => b.boards - a.boards || a.p.value.localeCompare(b.p.value)).slice(0, 10);
	});

	let away = $state(0);
	let f = $state('');
	const PAGE = 100;
	let shown = $state(PAGE);
	$effect(() => {
		away;
		f; // a new view starts from the top
		shown = PAGE;
	});
	const view = $derived.by(() => {
		const t = f.trim().toLowerCase();
		return rows.filter((r) => r.gaps.length === away && (!t || `${r.e.name} ${r.e.original} ${r.e.category} ${VENDOR_NAMES[r.e.vendor]}`.toLowerCase().includes(t)));
	});
	const TABS = ['Ready to build', '1 part away', '2 parts away', '3 parts away'];
	const gapText = (g: Gap) => g.alts.slice(0, 2).map((p) => p.value).join(' or ') + (g.alts.length > 2 ? ' or …' : '') + (g.n > 1 ? ` ×${g.n}` : '');
</script>

<svelte:head><title>What can I build · Akashic</title></svelte:head>

<h1>What can I build?</h1>
<p class="lede">List the parts you have and see which circuits they cover, and which are a part or two away. Parts come from the <a href="{base}/parts">catalog</a>: transistors, ICs, diodes, pots and the rest of what a parts list names by number. Resistors, capacitors, LEDs, jacks and the footswitch are not counted, since they go in everything. Your list is kept in this browser and goes nowhere else.</p>

<div class="bench">
	<div class="mine">
		<h2 class="label strong">Your parts <span class="mono dim">{owned.length}</span></h2>
		<form class="picker" onsubmit={submit}>
			<input type="search" bind:value={q} placeholder="TL072, 2N5088, B100k…" aria-label="Add a part" autocomplete="off" spellcheck="false" />
			<select bind:value={cat} aria-label="Kind of part">
				<option value="">All parts</option>
				{#each categories as c}<option value={c}>{PART_CATEGORY_NAMES[c] ?? c}</option>{/each}
			</select>
		</form>
		{#if skipped.length}<p class="note">Not in the catalog: <span class="mono">{skipped.join(', ')}</span></p>{/if}
		<ul class="suggest">
			{#each suggestions as p (p.key)}
				<li>
					<button type="button" onclick={() => add(p.key)} title="Add {p.value} to your parts">
						<span class="plus" aria-hidden="true">+</span><span class="mono val">{p.value}</span><span class="desc">{p.desc ?? p.types[0] ?? PART_CATEGORY_NAMES[p.category]}</span><span class="mono n">{p.count}</span>
					</button>
				</li>
			{:else}
				<li class="note">{q.trim() ? 'No part in the catalog matches.' : 'Every part here is on your list.'}</li>
			{/each}
		</ul>
		<p class="note">The number is how many circuits use the part. Enter adds the first match; a list separated by commas adds them all.</p>

		{#if owned.length}
			{#each categories as c}
				{@const items = owned.filter((k) => data.parts[at.get(k)!].category === c)}
				{#if items.length}
					<h3 class="label">{PART_CATEGORY_NAMES[c] ?? c}</h3>
					<ul class="have">
						{#each items as k (k)}
							{@const p = data.parts[at.get(k)!]}
							<li>
								<a class="mono val" href="{base}/parts/{p.slug}">{p.value}</a>
								<input type="number" min="1" inputmode="numeric" placeholder="any" value={inv[k] ?? ''} oninput={(ev) => setQty(k, ev.currentTarget.value)} aria-label="How many {p.value}" title="How many you have; empty means enough for any board" />
								<button type="button" class="x" onclick={() => remove(k)} aria-label="Remove {p.value}">×</button>
							</li>
						{/each}
					</ul>
				{/if}
			{/each}
			<button type="button" class="label clear" onclick={() => (inv = {})}>Clear the list</button>
		{/if}

		<h3 class="label">Take as on hand</h3>
		<div class="assume">
			{#each categories as c}
				<button type="button" class="chip" aria-pressed={assume.includes(c)} onclick={() => (assume = assume.includes(c) ? assume.filter((x) => x !== c) : [...assume, c])}>{PART_CATEGORY_NAMES[c] ?? c}</button>
			{/each}
		</div>
		<p class="note">A kind that is switched on is not counted: every board is taken to have them. Switches start that way.</p>
	</div>

	<div class="found">
		{#if !owned.length}
			<div class="empty">
				<p class="label strong">Nothing on the list yet</p>
				<p>Add a few parts on the left: start with the transistors and op amps in your drawer. Each one you add narrows the {Object.keys(data.needs.circuits).length.toLocaleString()} circuits with a parts list to the ones you can build now, and the ones you are a part or two short of.</p>
			</div>
		{:else}
			<div class="tabs" role="group" aria-label="How close">
				{#each TABS as name, n}
					<button type="button" class="chip" aria-pressed={away === n} onclick={() => (away = n)}>{name} <span class="count">{counts[n].toLocaleString()}</span></button>
				{/each}
			</div>
			{#if nextBuys.length}
				<div class="next">
					<span class="label">Finishes the most boards</span>
					{#each nextBuys as b (b.p.key)}
						<button type="button" class="chip buy" onclick={() => add(b.p.key)} title="{b.boards} circuits need only this. Add it to your parts.">+ {b.p.value} <span class="count">{b.boards}</span></button>
					{/each}
				</div>
			{/if}
			<label class="filter">
				<span class="label">Filter</span>
				<input type="search" bind:value={f} placeholder="fuzz, Big Muff, PedalPCB…" autocomplete="off" spellcheck="false" />
			</label>
			{#if view.length}
				<table class="sheet-table">
					<thead><tr><th>Circuit</th><th class="src">Source</th><th class="cat">Type</th><th class="n" title="Counted parts you have, of those the board takes">Parts</th>{#if away}<th>Missing</th>{/if}</tr></thead>
					<tbody>
						{#each view.slice(0, shown) as r (r.e.id)}
							<tr>
								<td>
									<a class="name" href="{base}/circuit/{r.e.file_id}">{r.e.name}</a>
									{#if r.e.original && r.e.original !== r.e.name}<span class="dim orig">{r.e.original}</span>{/if}
									{#if r.unread}<span class="dim orig" title="Rows of this parts list that name no part the catalog knows. Check the build document.">+{r.unread} unread {r.unread === 1 ? 'row' : 'rows'}</span>{/if}
								</td>
								<td class="src dim">{VENDOR_NAMES[r.e.vendor]}</td>
								<td class="cat dim">{r.e.category}</td>
								<td class="n mono">{r.total - r.gaps.length}/{r.total}</td>
								{#if away}
									<td class="gaps">
										{#each r.gaps as g}
											<button type="button" class="gap mono" onclick={() => add(g.alts[0].key)} title="Add {g.alts[0].value} to your parts">{gapText(g)}{#if g.have > 0}<span class="dim"> · have {g.have}</span>{/if}</button>
										{/each}
									</td>
								{/if}
							</tr>
						{/each}
					</tbody>
				</table>
				{#if shown < view.length}
					<div class="more-rows">
						<button class="btn ghost" type="button" onclick={() => (shown += PAGE * 2)}>Show {Math.min(PAGE * 2, view.length - shown)} more of {(view.length - shown).toLocaleString()} remaining</button>
					</div>
				{/if}
			{:else}
				<p class="note none">{f.trim() ? 'No circuit here matches the filter.' : away ? `No circuit is ${TABS[away].toLowerCase()}.` : 'Nothing is fully covered yet. The next tab shows what is one part away.'}</p>
			{/if}
		{/if}
	</div>
</div>

<style>
	.bench { display: grid; grid-template-columns: minmax(270px, 330px) minmax(0, 1fr); gap: 32px; align-items: start; margin-top: 8px; }
	h2 { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 10px; }
	h3 { margin: 18px 0 6px; }
	.dim { color: var(--ink-3); }
	.note { color: var(--ink-3); font-size: 13px; margin: 6px 0 0; }

	.picker { display: flex; gap: 6px; }
	.picker input, .picker select, .filter input { height: 38px; padding: 0 10px; border: 1px solid var(--rule-strong); border-radius: var(--radius); background: var(--sheet-2); color: var(--ink); font: inherit; }
	.picker input { flex: 1; min-width: 0; }
	.picker select { max-width: 42%; }
	.picker input:focus, .picker select:focus, .filter input:focus { outline: none; border-color: var(--coat); box-shadow: 0 0 0 3px var(--coat-tint); background: var(--sheet); }

	ul { list-style: none; margin: 0; padding: 0; }
	.suggest { margin-top: 8px; border: 1px solid var(--rule); border-radius: var(--radius); }
	.suggest li + li { border-top: 1px solid var(--rule); }
	.suggest li.note { padding: 8px 10px; margin: 0; }
	.suggest button { display: grid; grid-template-columns: 14px minmax(0, auto) minmax(0, 1fr) auto; gap: 8px; align-items: baseline; width: 100%; padding: 5px 10px; background: none; border: 0; text-align: left; cursor: pointer; color: inherit; font: inherit; }
	.suggest button:hover, .suggest button:focus-visible { background: var(--coat-tint); }
	.plus { color: var(--coat); font-weight: 700; }
	.val { font-weight: 600; overflow-wrap: anywhere; }
	.desc { color: var(--ink-3); font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.n { color: var(--ink-3); }

	.have li { display: grid; grid-template-columns: minmax(0, 1fr) 64px 28px; gap: 6px; align-items: center; padding: 3px 0; border-bottom: 1px solid var(--rule); }
	.have input { width: 100%; height: 28px; padding: 0 6px; border: 1px solid var(--rule); border-radius: var(--radius); background: transparent; color: var(--ink); font-family: var(--mono); font-size: 13px; text-align: right; }
	.have input:focus { outline: none; border-color: var(--coat); }
	.x { height: 28px; border: 0; background: none; color: var(--ink-3); font-size: 18px; line-height: 1; cursor: pointer; border-radius: var(--radius); }
	.x:hover { color: var(--warn); background: var(--sheet-2); }
	.clear { margin-top: 10px; background: none; border: 0; padding: 4px 0; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
	.clear:hover { color: var(--warn); }
	.assume { display: flex; flex-wrap: wrap; gap: 6px; }

	.empty { border: 1px dashed var(--rule-strong); border-radius: var(--radius); padding: 20px 22px; max-width: 62ch; }
	.empty p { margin: 0 0 6px; color: var(--ink-2); }
	.tabs, .next { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
	.next { margin-top: 14px; }
	.next .label { margin-right: 4px; }
	.buy { text-transform: none; letter-spacing: 0; font-family: var(--mono); font-weight: 400; font-size: 12px; border-style: dashed; }
	.filter { display: flex; align-items: center; gap: 10px; max-width: 420px; margin: 16px 0 6px; }
	.filter input { flex: 1; min-width: 0; }
	.name { font-weight: 600; }
	.orig { display: block; font-size: 13px; }
	.gaps { white-space: normal; }
	.gap { display: inline-block; margin: 2px 4px 2px 0; padding: 1px 7px; border: 1px dashed var(--rule-strong); border-radius: 999px; background: none; color: var(--ink); cursor: pointer; font-size: 12px; }
	.gap:hover { border-style: solid; border-color: var(--coat); background: var(--coat-tint); }
	.none { margin-top: 18px; font-size: 15px; }
	.more-rows { padding: 16px 10px; }

	@media (max-width: 860px) {
		.bench { grid-template-columns: minmax(0, 1fr); gap: 28px; }
		.src { display: none; }
	}
	@media (max-width: 560px) { .cat { display: none; } }
</style>
