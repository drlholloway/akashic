<script lang="ts">
	import '../app.css';
	import { page } from '$app/state';
	import { goto } from '$app/navigation';
	import { base } from '$app/paths';
	import type { Snippet } from 'svelte';
	import { currency, type Currency } from '$lib/currency.svelte';

	let { children, data }: { children: Snippet; data: { rates: import('$lib/currency.svelte').Rates | null } } = $props();
	$effect.pre(() => {
		currency.init(data.rates);
	});
	const currencyOptions: { value: Currency; label: string }[] = [
		{ value: 'USD', label: 'USD $' },
		{ value: 'EUR', label: 'EUR €' },
		{ value: 'GBP', label: 'GBP £' },
		{ value: 'native', label: 'As listed' }
	];
	let q = $state('');
	let titleblock: HTMLElement | undefined = $state();
	// Sticky table headers and the facet rail sit directly under the title block, so publish its
	// real height instead of guessing it: fonts, wrapping and zoom all change it.
	$effect(() => {
		if (!titleblock) return;
		const root = document.documentElement;
		const apply = () => root.style.setProperty('--titleblock-h', `${Math.round(titleblock!.getBoundingClientRect().height)}px`);
		apply();
		const ro = new ResizeObserver(apply);
		ro.observe(titleblock);
		return () => ro.disconnect();
	});
	$effect(() => {
		// keep the global field in sync with the index page's query
		q = page.url.pathname === `${base}/` ? (page.url.searchParams.get('q') ?? '') : q;
	});
	function submit(e: SubmitEvent) {
		e.preventDefault();
		const p = new URLSearchParams(page.url.pathname === `${base}/` ? page.url.searchParams : undefined);
		if (q.trim()) p.set('q', q.trim());
		else p.delete('q');
		goto(`${base}/?${p.toString()}`, { keepFocus: true, noScroll: true });
	}
	const nav = [
		{ href: `${base}/`, label: 'Circuits', match: (p: string) => p === `${base}/` || p.startsWith(`${base}/circuit/`) },
		{ href: `${base}/originals`, label: 'Originals', match: (p: string) => p.startsWith(`${base}/originals`) },
		{ href: `${base}/parts`, label: 'Parts', match: (p: string) => p.startsWith(`${base}/parts`) }
	];
</script>

<svelte:head>
	<title>PCB Schematic Library</title>
</svelte:head>

<header class="titleblock" bind:this={titleblock}>
	<a class="brand" href="{base}/">
		<span class="brand-name">PCB Schematic Library</span>
		<span class="brand-sub">DIY pedal circuits, parts &amp; where to buy the board</span>
	</a>
	<form class="search" role="search" onsubmit={submit}>
		<label class="sr-only" for="q">Search circuits, originals, parts</label>
		<input id="q" type="search" bind:value={q} placeholder="Search: Rat, LM308, phaser, 125B, PedalPCB…" autocomplete="off" spellcheck="false" enterkeyhint="search" />
		<button class="btn" type="submit">Search</button>
	</form>
	<nav aria-label="Sections">
		{#each nav as n}
			<a href={n.href} aria-current={n.match(page.url.pathname) ? 'page' : undefined}>{n.label}</a>
		{/each}
		<label class="currency" title={currency.rates.date ? `Converted at ECB rates from ${currency.rates.date}` : 'No exchange rates loaded'}>
			<span class="sr-only">Show prices in</span>
			<select value={currency.selected} onchange={(e) => currency.set(e.currentTarget.value as Currency)} disabled={!currency.rates.date}>
				{#each currencyOptions as o}
					<option value={o.value}>{o.label}</option>
				{/each}
			</select>
		</label>
	</nav>
</header>

<main>
	{@render children()}
</main>

<footer>
	<p>Index of circuits published by PedalPCB, Aion FX, Madbean Pedals, GuitarPCB, Fuzz Dog, Sheepy Love, Dead End FX, Moonn Electronics, Five Cats Pedals, Parasit Studio, PCB Guitar Mania, Dead Astronaut FX, shared PCBWay projects, and the Bent Fishbowl schematic blog. Names, part values and prices are indexed for reference; build documents and schematics belong to their vendors and are linked, not copied. Buy the board from the vendor.</p>
</footer>

<style>
	.titleblock {
		display: grid;
		grid-template-columns: auto 1fr auto;
		grid-template-areas: 'brand search nav';
		align-items: center;
		gap: 16px var(--gutter);
		padding: 12px var(--gutter);
		border-bottom: 1px solid var(--rule-strong);
		background: var(--sheet);
		position: sticky;
		top: 0;
		z-index: 5;
	}
	.brand { grid-area: brand; display: flex; flex-direction: column; line-height: 1.1; }
	.brand:hover { text-decoration: none; }
	.brand-name { font-family: var(--label); font-weight: 700; font-size: 20px; letter-spacing: 0.06em; text-transform: uppercase; }
	.brand-sub { font-size: 12px; color: var(--ink-3); }
	.search { grid-area: search; display: flex; gap: 8px; max-width: 720px; width: 100%; justify-self: center; }
	.search input {
		flex: 1;
		min-width: 0;
		height: 40px;
		padding: 0 12px;
		border: 1px solid var(--rule-strong);
		border-radius: var(--radius);
		background: var(--sheet-2);
	}
	.search input:focus { border-color: var(--coat); background: var(--sheet); outline: none; box-shadow: 0 0 0 3px var(--coat-tint); }
	nav { grid-area: nav; display: flex; gap: 4px; align-items: center; }
	.currency select {
		margin-left: 8px;
		border: 1px solid var(--rule-strong);
		border-radius: var(--radius);
		background: var(--sheet);
		padding: 5px 8px;
		font-family: var(--label);
		font-weight: 600;
		font-size: 13px;
		letter-spacing: 0.06em;
		text-transform: uppercase;
	}
	.currency select:disabled { opacity: 0.5; }
	nav a {
		font-family: var(--label);
		font-weight: 600;
		font-size: 14px;
		letter-spacing: 0.1em;
		text-transform: uppercase;
		padding: 8px 10px;
		border-bottom: 2px solid transparent;
		color: var(--ink-2);
	}
	nav a:hover { text-decoration: none; color: var(--ink); }
	nav a[aria-current='page'] { color: var(--ink); border-bottom-color: var(--coat); }
	main { min-height: 70dvh; }
	footer { padding: 32px var(--gutter) 48px; border-top: 1px solid var(--rule); color: var(--ink-3); font-size: 13px; max-width: 80ch; }
	@media (max-width: 860px) {
		.titleblock {
			grid-template-columns: 1fr auto;
			grid-template-areas: 'brand nav' 'search search';
			gap: 10px 12px;
			padding: 10px 16px;
		}
		.brand-name { font-size: 17px; }
		.brand-sub { display: none; }
		.search .btn { display: none; }
		nav a { padding: 6px 8px; font-size: 13px; }
	}
</style>
