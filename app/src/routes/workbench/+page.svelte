<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>Workbench · Akashic</title>
	<meta name="description" content="A pedal builder's notes: where to buy which parts, how to build a board, and the sites and tools worth keeping open." />
</svelte:head>

<header class="head">
	<h1>Workbench</h1>
	<p class="lede">The library tells you what a circuit needs. These are the notes I keep looking up once I have picked one: where the parts come from, the order I build in, and the sites and tools I keep open.</p>
</header>

<section>
	<h2 class="label strong">What's here</h2>
	<ul>
		<li><a href="{base}/workbench/sourcing">Sourcing</a>: which shop I use for which part, and the brands I stick to, from resistors to wire.</li>
		<li><a href="{base}/workbench/building">Building</a>: the soldering iron and solder, setting up, and the order the parts go on the board.</li>
		<li><a href="{base}/workbench/bench">My bench</a>: the circuits you keep, with a note on each, saved in your browser. Export it or share it as a link.</li>
		<li><a href="{base}/workbench/build">What can I build</a>: list the parts in your drawers and see which circuits they cover, and which are a part or two away.</li>
		<li><a href="{base}/workbench/links">Links</a>: books, courses, forums, calculators and guides for having your own boards made.</li>
	</ul>
</section>

<section>
	<h2 class="label strong">Building your first pedal?</h2>
	<p>
		Start with a kit, not a bare board. The
		<a href="https://shop.mas-effects.com/products/ultimate-beginner-pedal-kit" target="_blank" rel="noopener">Ultimate Beginner Pedal Kit</a>
		from Mas Effects has everything but the soldering iron and takes you from zero to a working pedal. After that, pick a
		board from the <a href="{base}/">circuits</a>, read <a href="{base}/workbench/building">Building</a>, and order parts with
		<a href="{base}/workbench/sourcing">Sourcing</a> open.
	</p>
</section>
