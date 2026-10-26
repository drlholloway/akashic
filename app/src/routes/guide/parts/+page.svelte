<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>Originals and parts · Guide · Akashic</title>
	<meta name="description" content="Compare every board based on one pedal, find every circuit that uses a part, and read a part's datasheets and transistor substitutes." />
</svelte:head>

<header class="head">
	<h1>Originals and parts</h1>
	<p class="lede">
		Two cross-references no single vendor can give you: every board based on the same pedal, and every circuit that uses the same
		part.
	</p>
</header>

<section>
	<h2 class="label strong">Originals</h2>
	<p>
		<a href="{base}/originals">Originals</a> lists the commercial pedals the circuits are based on, by brand and then pedal, with:
	</p>
	<ul>
		<li><strong>Circuits</strong>: how many boards, layouts and schematics copy or adapt it,</li>
		<li><strong>Built on</strong>: how many of those are PCBs and how many are vero, tagboard or other layouts, each count a link to just those,</li>
		<li><strong>Sources</strong> and <strong>Category</strong>.</li>
	</ul>
	<p>
		Type in <em>Filter</em> to find a pedal (<span class="mono">klon</span>, <span class="mono">tube screamer</span>), then pick it to open
		every circuit based on it in the Circuits table. From there the usual filters apply: only the ones in a 1590B, only the ones in
		stock, only the vero layouts. <a href="{base}/?based=Electro-Harmonix%20Big%20Muff%20Pi">Every Big Muff Pi</a> is a good place to
		see how far the boards of one pedal differ.
	</p>
	<p>
		Different sources spell the same pedal differently (“Pro Co RAT Distortion”, “ProCo RAT”). Akashic files the spellings under one
		name, but a pedal and its later versions, such as the TS808 and the TS9 Tube Screamers, stay apart.
	</p>
</section>

<section>
	<h2 class="label strong">The parts cross-reference</h2>
	<p>
		<a href="{base}/parts">Parts</a> lists every part named by number across all the parts lists, grouped by kind: diodes, pots
		(by taper, then value), ICs, transistors, switches, trimmers, optocouplers, inductors, transformers and crystals. The number beside
		each is how many circuits use it. Resistors and capacitors are left out, since every circuit has them. <em>Filter</em> matches the
		part number and its description, so <span class="mono">delay</span> finds the delay chips and <span class="mono">jfet</span> the JFETs.
	</p>
</section>

<section>
	<h2 class="label strong">A part's page</h2>
	<p>Open a part, such as the <a href="{base}/parts/ic-lm308">LM308</a>, and you get:</p>
	<ul>
		<li><strong>What it is</strong> and how the parts lists describe it.</li>
		<li>
			<strong>The datasheet</strong>, linked from the maker's own site. For a discontinued part whose maker no longer publishes one,
			Akashic keeps an archived copy, and a part made by several fabs lists each maker's sheet. A part that is made again under a new
			number links the new part's sheet first.
		</li>
		<li><strong>Every circuit that uses it</strong>, in the same table as the Circuits page.</li>
	</ul>

	<h3>Transistor substitutes</h3>
	<p>
		A transistor's page, such as the <a href="{base}/parts/q-2n5088">2N5088</a>, suggests substitutes from a database of transistor
		limits. Candidates share the material (silicon or germanium) and the polarity or channel, and are ranked by how close their gain,
		voltage, current, power and speed are. They come in two lists: parts that other boards in the library already use, and the
		closest by the numbers.
	</p>
	<p>
		The database has no pinouts or packages. Before you drop a substitute in, check its datasheet: a different pin order means turning
		it on the board, and a different gain changes the sound, which is the point in a fuzz and a problem in a buffer.
	</p>

	<h3>Zeners</h3>
	<p>
		A parts list that gives only a zener's voltage, such as <a href="{base}/parts/d-9v1">9V1</a>, gets a page listing the zener parts
		of that voltage, their power rating and package, with a note on which size fits a pedal board.
	</p>
</section>

<section>
	<h2 class="label strong">From a parts list to a part</h2>
	<p>
		On any circuit page, the <em>Normalized</em> column of the parts list links each numbered part to its page, so you can go from a
		board you like to every other board that uses its chip. From a part's page, <em>What can I build</em> on the
		<a href="{base}/guide/workbench">Workbench</a> takes the next step: which circuits the parts you have would finish.
	</p>
</section>
