<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>Guide · Akashic</title>
	<meta name="description" content="How to use Akashic: find a circuit, read its parts list, compare boards of the same pedal, and see what you can build with the parts you have." />
</svelte:head>

<header class="head">
	<h1>How to use Akashic</h1>
	<p class="lede">
		Akashic indexes thousands of DIY guitar-pedal circuits from PCB vendors, layout sites, blogs and archives, with each one's parts
		list read into a single database. It does not sell anything: every circuit links back to the place you get the board, the layout or
		the schematic. This guide shows how to find what you are after and how far to trust what you find.
	</p>
</header>

<section>
	<h2 class="label strong">A first look</h2>
	<ol>
		<li>Type a pedal, a part or a kind of effect in the search box at the top, for example <a href="{base}/?q=rat">Rat</a>, and press Enter.</li>
		<li>Narrow the list with the filters on the left: vendor, category, enclosure, knob count, controls, how it is built.</li>
		<li>Open a circuit. Its page has the vendor and price, the build document, the controls and the full parts list.</li>
		<li>Press <span class="mono">+ My bench</span> to keep it, then buy the board from the vendor with the button at the top of the page.</li>
	</ol>
</section>

<section>
	<h2 class="label strong">Questions it answers in one step</h2>
	<table class="sheet-table try">
		<thead><tr><th>Go to</th><th>What you get</th></tr></thead>
		<tbody>
			<tr><td><a href="{base}/?based=ProCo%20RAT">Based on the ProCo RAT</a></td><td>Every board and layout that clones one pedal, from every source, in one list.</td></tr>
			<tr><td><a href="{base}/parts/ic-lm308">LM308</a></td><td>Every circuit whose parts list names a part, with its datasheet.</td></tr>
			<tr><td><a href="{base}/?enc=125B&knobs=3">125B, 3 knobs</a></td><td>Boards that fit the enclosure you have drilled.</td></tr>
			<tr><td><a href="{base}/workbench/build">What can I build</a></td><td>The circuits the parts in your drawers already cover, and the ones a part or two away.</td></tr>
			<tr><td><a href="{base}/originals">Originals</a></td><td>The commercial pedals behind the boards, with how many clones each has.</td></tr>
		</tbody>
	</table>
</section>

<section>
	<h2 class="label strong">The words Akashic uses</h2>
	<dl class="terms">
		<div><dt class="label">Circuit</dt><dd>One board, layout or schematic from one source. The same pedal from two vendors is two circuits.</dd></div>
		<div><dt class="label">Based on</dt><dd>The commercial pedal a circuit clones or adapts, the <em>original</em>. Sources spell them differently; Akashic files “Pro Co RAT Distortion” and “ProCo RAT” under one original.</dd></div>
		<div><dt class="label">Source</dt><dd>Where a circuit comes from: a PCB shop, a layout blog, a code repository, a schematic archive. The <a href="{base}/guide/questions">Questions</a> page lists the kinds.</dd></div>
		<div><dt class="label">Build</dt><dd>What you build it on: a bought PCB, or vero (stripboard), perfboard, tagboard, turret board or point to point from a layout drawing.</dd></div>
		<div><dt class="label">Parts list</dt><dd>The bill of materials (BOM), one row per part. <em>Ref</em> is the designator printed on the board (R1, C4, Q2).</dd></div>
		<div><dt class="label">Normalized</dt><dd>A value rewritten one way, so 4k7, 4.7K and 4700 all read 4k7 and match each other across every source.</dd></div>
		<div><dt class="label">Box</dt><dd>The enclosure size, in Hammond's names (1590A, 1590B, 125B, 1590BB…).</dd></div>
	</dl>
</section>

<section>
	<h2 class="label strong">Install it and use it offline</h2>
	<p>
		Akashic loads its index once, then searches in your browser. Once it has loaded, the search, the filters, the Originals, Parts and
		Workbench pages and this guide work without a connection; a circuit or part page works offline once you have opened it. To keep it
		as an app, use your browser's install option: <em>Install</em> in Chrome or Edge's address bar or menu, <em>Add to Dock</em> in
		Safari on a Mac, or <em>Add to Home Screen</em> from the share menu on an iPhone or iPad and the menu on Android. The library is
		refreshed every week, and the app picks up the new data the next time it opens online.
	</p>
</section>

<section>
	<h2 class="label strong">In this guide</h2>
	<ul>
		<li><a href="{base}/guide/search">Searching and filtering</a>: what the search box matches, the filters, sorting, and sharing a search.</li>
		<li><a href="{base}/guide/circuit">Reading a circuit page</a>: the header, the buttons, the schematic and the parts list with its marks.</li>
		<li><a href="{base}/guide/parts">Originals and parts</a>: comparing clones of one pedal, a part's page, datasheets and substitutes.</li>
		<li><a href="{base}/guide/workbench">My bench and What can I build</a>: keeping circuits, notes, sharing, and matching your parts.</li>
		<li><a href="{base}/guide/questions">Questions</a>: prices, sources, missing schematics, privacy and reporting a mistake.</li>
	</ul>
</section>
