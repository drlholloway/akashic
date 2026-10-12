<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>Building · Workbench · Akashic</title>
	<meta name="description" content="What you need to build a guitar pedal and the order to build it in: soldering iron, solder, setup and the build order from resistors to boxing." />
</svelte:head>

<header class="head">
	<h1>Building</h1>
	<p class="lede">Building a PCB is a straightforward process, but there are gotchas. This is the equipment I use and the steps I take.</p>
</header>

<section>
	<h2 class="label strong">Equipment</h2>
	<h3>Soldering iron</h3>
	<p>
		These are personal. I really like Metcal, and one can be had on eBay for about the cost of a decent new iron if you
		watch: I paid a little under $200 shipped for an MX-500P-II with the handpiece and stand, and about $175 for a
		desoldering gun, which makes desoldering a little easier. I would not go this way until you know you want to keep
		building pedals.
	</p>
	<p>
		To start, get a decent iron with replaceable tips, adjustable temperature and a stand. Spring for a soldering mat too, so
		the tip does not burn your desk.
	</p>
	<h3>Solder</h3>
	<p>There are two broad kinds: leaded and lead-free. I lean toward lead-free.</p>
</section>

<section>
	<h2 class="label strong">Before you solder</h2>
	<h3>Set up</h3>
	<p>
		Clean the area where you are going to work; a clean bench makes for a much easier time. Lay out everything you need and
		check that it all works.
	</p>
	<h3>Read the instructions</h3>
	<p>
		It sounds obvious, but we often jump in and start soldering, only to find we have messed something up. Read the build
		document through a few times, so you know which parts you need and what the PCB and the schematic look like. Every
		<a href="{base}/">circuit</a> here links its build document and lists its parts; where to order them is under
		<a href="{base}/workbench/sourcing">Sourcing</a>.
	</p>
</section>

<section>
	<h2 class="label strong">Build order</h2>
	<p>
		Build from the shortest part to the tallest: resistors first, then up to the pots and the off-board wiring. Have the
		drilled enclosure ready before you solder the pots, switches and other off-board parts. It works as a template and shows
		whether everything fits.
	</p>
	<ol>
		<li>Prepare the enclosure</li>
		<li>Resistors and diodes</li>
		<li>Sockets</li>
		<li>Capacitors</li>
		<li>Transistors</li>
		<li>Potentiometers and switches</li>
		<li>Off-board wires, DC jack, audio jacks</li>
		<li>Test</li>
		<li>Box</li>
		<li>Play</li>
	</ol>
</section>
