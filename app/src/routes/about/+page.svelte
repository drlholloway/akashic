<script lang="ts">
	import { base } from '$app/paths';
	import { COFFEE_URL, ISSUES_URL, MAKER_NAME, MAKER_URL, REPO_URL } from '$lib/site';

	let { data } = $props();
	const m = $derived(data.meta);
	const fmt = (n: number) => n.toLocaleString('en-US');
	const refreshed = $derived(
		new Date(m.generated_at).toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })
	);
</script>

<svelte:head>
	<title>About · Akashic</title>
	<meta name="description" content="What Akashic is, where its circuits and parts lists come from, and how to read them." />
</svelte:head>

<div class="about">
	<header class="head">
		<h1>About Akashic</h1>
		<p class="lede">
			A searchable library of DIY guitar-pedal circuits, gathered from the build documents that PCB vendors and designers publish.
		</p>
		<dl class="figures">
			<div><dt class="label">Circuits</dt><dd class="mono">{fmt(m.circuits)}</dd></div>
			<div><dt class="label">Sources</dt><dd class="mono">{fmt(m.sources)}</dd></div>
			<div><dt class="label">Parts rows</dt><dd class="mono">{fmt(m.parts_rows)}</dd></div>
			<div><dt class="label">Last refreshed</dt><dd class="mono">{refreshed}</dd></div>
		</dl>
	</header>

	<section>
		<h2 class="label strong">What's here</h2>
		<p>
			Every circuit has what it is based on, the vendor and price with a link to buy it, the build document, the controls and
			enclosure, and its parts list. Part values are normalized (4k7, 4.7K and 4700 are one value), so the same part matches
			across every vendor.
		</p>
		<ul>
			<li><a href="{base}/">Circuits</a>: search by name, original, part, category, vendor or enclosure, and filter the list.</li>
			<li><a href="{base}/originals">Originals</a>: every board based on the same commercial pedal, side by side.</li>
			<li><a href="{base}/parts">Parts</a>: which circuits use a part (every LM308, every 2N5088, every A100k).</li>
		</ul>
	</section>

	<section>
		<h2 class="label strong">Where the parts lists come from</h2>
		<p>
			Most parts lists are read from the tables in the vendor's build document or from the interactive BOM that comes with a
			KiCad project. Those are exact. Some documents only have a picture of the table or of the schematic; those are read by
			machine, and the circuit page marks each value so you know how far to trust it:
		</p>
		<dl class="marks">
			<div><dt><span class="src">ocr</span></dt><dd>read from an image of the parts list</dd></div>
			<div><dt><span class="src">sch</span></dt><dd>paired from the labels on the schematic drawing</dd></div>
			<div><dt><span class="src fixed">fixed</span></dt><dd>corrected by hand, where the source had a typo or the reading was wrong</dd></div>
		</dl>
		<p>Before you order parts, check marked values against the build document linked on the circuit page.</p>
	</section>

	<section>
		<h2 class="label strong">Prices and availability</h2>
		<p>
			Prices are the vendor's list price, shown in dollars by default and converted with the European Central Bank's exchange
			rates; the currency menu switches to euros, pounds or the vendor's own listing. Prices, stock and new boards are
			refreshed every week. A board a vendor stops listing stays in the library, marked no longer listed with the date it was
			last seen.
		</p>
	</section>

	<section>
		<h2 class="label strong">What is copied and what is linked</h2>
		<p>
			Names, part values, prices and links are indexed. Build documents and schematics belong to their authors: Akashic links
			to them instead of copying them. Buy the board from the vendor; that is what keeps them publishing.
		</p>
	</section>

	<section>
		<h2 class="label strong">Something wrong?</h2>
		<p>
			A parts list that reads wrong, a vendor to add, a bug or an idea:
			<a href={ISSUES_URL} target="_blank" rel="noopener">open an issue on GitHub</a>. Every circuit page has a link that fills in
			the board for you. Corrections go into the library and stay fixed through every refresh.
		</p>
	</section>

	<section>
		<h2 class="label strong">Who makes it</h2>
		<p>
			Akashic is made by <a href={MAKER_URL} target="_blank" rel="noopener">{MAKER_NAME}</a> on evenings and weekends. The code
			is on <a href={REPO_URL} target="_blank" rel="noopener">GitHub</a>, and the <a href="{base}/changes">changelog</a> lists what
			changed each week. It works offline once loaded and can be installed as an app from your browser's menu. If it saved
			you a build, <a href={COFFEE_URL} target="_blank" rel="noopener">buy me a coffee</a>.
		</p>
	</section>
</div>

<style>
	.about { padding: 24px var(--gutter) 48px; max-width: 900px; }
	.head h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.lede { max-width: 70ch; color: var(--ink-2); margin: 0 0 18px; }
	.figures { display: flex; flex-wrap: wrap; gap: 8px 32px; margin: 0; padding-bottom: 18px; border-bottom: 1px solid var(--rule-strong); }
	.figures div { display: grid; gap: 2px; }
	.figures dd { margin: 0; font-size: 20px; font-weight: 600; }
	section { margin-top: 28px; }
	section h2 { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 10px; }
	section p, section li { max-width: 70ch; }
	section p { margin: 0 0 10px; }
	section ul { margin: 0 0 10px; padding-left: 18px; }
	section li { margin-bottom: 4px; }
	section a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	section a:hover { text-decoration-color: var(--coat); }
	.marks { margin: 0 0 10px; display: grid; gap: 6px; }
	.marks div { display: grid; grid-template-columns: 7ch 1fr; gap: 12px; align-items: baseline; }
	.marks dt, .marks dd { margin: 0; }
	.src { padding: 0 4px; border: 1px solid var(--rule-strong); border-radius: 3px; font-family: var(--label); font-weight: 600; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); }
	.src.fixed { border-color: var(--coat); color: var(--coat); }
</style>
