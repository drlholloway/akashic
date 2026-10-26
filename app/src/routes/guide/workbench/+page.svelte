<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>My bench and What can I build · Guide · Akashic</title>
	<meta name="description" content="Keep circuits on your bench with notes, export or share it, and match the parts in your drawers against every parts list in Akashic." />
</svelte:head>

<header class="head">
	<h1>My bench and What can I build</h1>
	<p class="lede">
		Two tools under <a href="{base}/workbench">Workbench</a> for when you are choosing a build: a bench to keep the circuits you are
		considering, and a parts matcher that shows what the parts you already have can build. Both are kept in your browser. Akashic has
		no accounts and nothing you enter leaves your device unless you export it or share a link.
	</p>
</header>

<section>
	<h2 class="label strong">My bench</h2>
	<p>
		Press <span class="mono">+ My bench</span> on a circuit's page to keep it. A note field opens under the buttons for anything you
		want to remember (“try 2N5088s”, “order with the Klon parts”), up to 300 characters. Kept circuits are tagged <em>Bench</em> in
		every circuits table, and <em>On my bench</em> at the top of the Circuits filters lists only them.
	</p>
	<p><a href="{base}/workbench/bench">Workbench → My bench</a> lists them with their notes and the date you added each, and lets you:</p>
	<ul>
		<li><strong>Open in Circuits</strong>, to filter and sort your bench like any other list,</li>
		<li><strong>What can I build from it</strong>, to match your parts against only these circuits,</li>
		<li><strong>Copy share link</strong>, a link that opens the same circuits for someone else, who can add them to their own bench. The link carries the circuits, not your notes.</li>
		<li><strong>Export</strong> and <strong>Import</strong>, a file holding your bench, your notes and your What can I build parts list. Importing merges: circuits already on the bench keep their note unless it is empty, and parts are added to your list.</li>
	</ul>
	<p>
		Because the bench lives in this browser, it is gone if you clear the site's data, and it does not follow you to another device or
		browser. Safari also clears it after seven days without a visit unless Akashic is added to the home screen or the Dock. Export it
		now and then if it matters to you.
	</p>
</section>

<section>
	<h2 class="label strong">What can I build</h2>
	<p>
		<a href="{base}/workbench/build">What can I build</a> takes the parts in your drawers and checks them against every parts list in
		the library.
	</p>
	<h3>Listing your parts</h3>
	<ul>
		<li>Type a part number in <em>Your parts</em>; the suggestions show how many circuits use each. Click one to add it, or press Enter to add the first.</li>
		<li>Paste a list separated by commas (<span class="mono">TL072, 2N5088, 1N914, B100k</span>) to add them all at once. Anything the catalog does not know is listed so you can check the spelling.</li>
		<li>Give a quantity if it matters. Left empty, a part counts as enough for any board.</li>
		<li>Only parts named by number are counted: transistors, ICs, diodes, pots, switches and the like. Resistors, capacitors, LEDs, jacks and the footswitch are taken as on hand.</li>
		<li><em>Take as on hand</em> stops counting a whole kind of part. Switches start switched on; turn on pots if you keep a drawer of them.</li>
	</ul>
	<h3>Reading the results</h3>
	<ul>
		<li><strong>Ready to build</strong>, <strong>1 part away</strong>, <strong>2 parts away</strong> and <strong>3 parts away</strong> sort the circuits by how many counted parts you are missing.</li>
		<li><strong>Parts</strong> shows how many of the board's counted parts you have, out of how many it needs.</li>
		<li><strong>Missing</strong> lists what you lack. Click a missing part to add it to your list once you have bought it.</li>
		<li><strong>Finishes the most boards</strong> suggests the parts that would move the most circuits up to ready to build. It is a short shopping list.</li>
		<li><strong>+ unread rows</strong> on a circuit means some rows of its parts list name nothing the catalog knows. Check those against the build document.</li>
		<li><em>Filter</em> narrows the list (<span class="mono">fuzz</span>, <span class="mono">Big Muff</span>), and <em>Surprise me</em> opens one of the listed circuits at random.</li>
	</ul>
	<p>
		The matching is generous where builders are. A row that offers alternatives (“2N5088 or 2N5089”) needs only one of them, a plain
		part number matches its fuller spellings (BC549 and BC549C, 4558 and NE4558N), and a zener given by voltage matches the zener
		parts of that voltage.
	</p>
</section>

<section>
	<h2 class="label strong">The rest of the Workbench</h2>
	<p>
		<a href="{base}/workbench/sourcing">Sourcing</a>, <a href="{base}/workbench/building">Building</a> and
		<a href="{base}/workbench/links">Links</a> are one builder's notes: where to buy which parts, the order to build a board in, and
		the books, forums and calculators worth keeping open. Unlike the rest of Akashic, they are opinion. If this is your first pedal,
		start with the <a href="{base}/workbench">Workbench overview</a>.
	</p>
</section>
