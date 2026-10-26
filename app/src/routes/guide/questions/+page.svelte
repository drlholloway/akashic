<script lang="ts">
	import { base } from '$app/paths';
	import { ISSUES_URL, REPO_URL } from '$lib/site';
</script>

<svelte:head>
	<title>Questions · Guide · Akashic</title>
	<meta name="description" content="Answers about Akashic: where circuits come from, prices and stock, missing schematics, what is kept in your browser, and how to report a mistake." />
</svelte:head>

<header class="head">
	<h1>Questions</h1>
	<p class="lede">The things people ask most, answered briefly.</p>
</header>

<section>
	<h2 class="label strong">Can I buy a board from Akashic?</h2>
	<p>
		No. Akashic is an index. Every circuit links to the place you get it, and buying there is what keeps vendors and designers
		publishing.
	</p>
</section>

<section>
	<h2 class="label strong">Where do the circuits come from?</h2>
	<p>From several kinds of source. The first button on a circuit's page says which kind it is:</p>
	<dl class="terms">
		<div><dt class="label">PCB shops</dt><dd>Sell the bare board, with a free build document. Most of the library.</dd></div>
		<div><dt class="label">Kits</dt><dd>Sell the board with every part.</dd></div>
		<div><dt class="label">Shared projects</dt><dd>A board shared on a board maker's site (PCBWay, OSH Park), which you order from that maker.</dd></div>
		<div><dt class="label">Repositories</dt><dd>Free gerbers and files on GitHub, to send to any board maker.</dd></div>
		<div><dt class="label">Layouts</dt><dd>Free vero, perfboard, tagboard and turret drawings: no board to buy, you build on stock board.</dd></div>
		<div><dt class="label">Blogs and archives</dt><dd>Schematics, often traced from the original pedal, with no board at all.</dd></div>
	</dl>
	<p>The <em>Sources</em> list at the foot of every page names them all and links to each.</p>
</section>

<section>
	<h2 class="label strong">Why don't I see the schematic?</h2>
	<p>
		Build documents and schematics belong to their authors, so Akashic links to them instead of copying them. The circuit page says
		where the schematic is, often down to the page of the build document. Where a schematic has been redrawn in KiCad or its author
		shares it under an open license, it is shown on the page.
	</p>
</section>

<section>
	<h2 class="label strong">Why is the price different at the vendor?</h2>
	<p>
		Prices are the vendor's list price, refreshed weekly, without shipping or tax. If you have chosen a currency other than the
		vendor's, the price is converted at the European Central Bank's rate; choose <em>As listed</em> in the Prices menu to see the
		vendor's own figure. Stock is from the same weekly refresh, so a board can sell out in between.
	</p>
</section>

<section>
	<h2 class="label strong">A board says “No longer listed”</h2>
	<p>
		The vendor stopped listing it. Akashic keeps it, with the date it was last seen, because the parts list and the clone it
		belongs to are still useful. The vendor's links may no longer work. Boards from stores that have closed are kept the same way.
	</p>
</section>

<section>
	<h2 class="label strong">A parts list is wrong</h2>
	<p>
		Check whether the value is marked <span class="src">ocr</span> or <span class="src">sch</span>: those were read by machine from
		an image (see <a href="{base}/guide/circuit">Reading a circuit page</a>). Then press <em>Report a wrong parse</em> above the
		parts list. It opens a GitHub issue with the circuit filled in; add the rows that are wrong and what the build document says.
		Corrections go into the library and stay fixed through every refresh. You need a free GitHub account to open an issue.
	</p>
</section>

<section>
	<h2 class="label strong">Can you add a vendor, or my boards?</h2>
	<p>
		<a href={ISSUES_URL} target="_blank" rel="noopener">Open an issue</a> and choose <em>Vendor request</em>. A source that publishes
		its parts lists (a build document, a BOM file, a parts table on the page) can be added with its full parts lists; one that does
		not can still be listed.
	</p>
</section>

<section>
	<h2 class="label strong">What does Akashic keep about me?</h2>
	<p>
		Nothing. There are no accounts. My bench, your notes, your What can I build list and your currency choice are kept in your
		browser and go nowhere unless you export them or send a share link. Clearing the site's data erases them, so
		<a href="{base}/guide/workbench">export your bench</a> if you want to keep it.
	</p>
</section>

<section>
	<h2 class="label strong">How often does it change?</h2>
	<p>
		Every week: prices, stock and new boards from every source, plus whatever was fixed or added. The
		<a href="{base}/changes">changelog</a> lists each week's changes.
	</p>
</section>

<section>
	<h2 class="label strong">I want to help, or run it myself</h2>
	<p>
		Akashic's code is on <a href={REPO_URL} target="_blank" rel="noopener">GitHub</a>. The
		<a href="{REPO_URL}/wiki" target="_blank" rel="noopener">project wiki</a> covers how the parts lists are read, running the scraper,
		fixing a parse and adding a source.
	</p>
</section>
