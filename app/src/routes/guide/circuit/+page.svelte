<script lang="ts">
	import { base } from '$app/paths';
</script>

<svelte:head>
	<title>Reading a circuit page · Guide · Akashic</title>
	<meta name="description" content="What each part of an Akashic circuit page tells you: the header, the buttons, the schematic, and the parts list with its OCR and schematic marks." />
</svelte:head>

<header class="head">
	<h1>Reading a circuit page</h1>
	<p class="lede">
		Every circuit has a page with what it is, where to get it and what goes on it. From top to bottom, this is what each part tells
		you. <a href="{base}/circuit/pedalpcb-pcb012">PedalPCB's Muffin Fuzz</a> is a good one to keep open beside this.
	</p>
</header>

<section>
	<h2 class="label strong">The header</h2>
	<ul>
		<li><strong>The faceplate</strong> on the left is drawn from the circuit's enclosure and controls, with the knobs named. The caption gives the box and the knob count.</li>
		<li><strong>Vendor and SKU</strong> above the name; the vendor links to all of that vendor's circuits.</li>
		<li><strong>Based on</strong> names the original, which links to every circuit based on it, and counts the other boards that clone it. Where the designer of the original also sells a board, that board is linked here.</li>
		<li><strong>Category, Controls, Difficulty, Build.</strong> A control name links to every circuit with a control like it.</li>
		<li><strong>Price</strong> in your chosen currency, with the vendor's own price beside it when it was converted, and the stock: in stock, out of stock or no longer listed.</li>
		<li><strong>Also as</strong>: a stripboard or other layout the same source publishes for the circuit.</li>
	</ul>
	<p>
		A layout (vero, tagboard and the rest) shows the board size, the number of track cuts and wire links, and whether the layout's source
		marks it <em>Verified</em>, meaning someone has built it and it works. An unverified layout may still have a mistake in it.
	</p>
	<p>
		A board the vendor has stopped listing stays in the library with a <em>No longer listed</em> note and the last date it was seen.
		Its links may no longer work.
	</p>
</section>

<section>
	<h2 class="label strong">The buttons</h2>
	<p>The first button is where you get the circuit, and its label says what you will find there:</p>
	<ul>
		<li><em>Buy the PCB at …</em> for a shop,</li>
		<li><em>Get the gerbers at …</em> for a free board in a code repository, which you order from a board maker,</li>
		<li><em>Order the board at …</em> for a project shared on a board maker's site,</li>
		<li><em>Open the layout at …</em>, <em>Read the post at …</em> or <em>Open the schematic at …</em> for free layouts, blogs and archives,</li>
		<li><em>See the kit at …</em> for a complete kit.</li>
	</ul>
	<p>
		<em>Build document</em> opens the vendor's PDF, with its version where the vendor gives one. Other files the source shares, such as
		drill templates, gerbers or a KiCad project, get a button each. <span class="mono">+ My bench</span> keeps the circuit, and once it
		is on your bench a note field opens under the buttons. Some sources carry a <em>Heads up</em> line, a caution about that vendor's
		documents worth reading before you order.
	</p>
	<p>
		A few designers sell boards by message rather than through a shop. Their circuits say so under the title, with a link to message
		them.
	</p>
</section>

<section>
	<h2 class="label strong">The schematic</h2>
	<p>
		Schematics belong to the people who drew them, so Akashic links to them rather than copying them. The Schematic section says where
		this circuit's is: the build document and the page it is on, the blog post, the archive file or the designer's KiCad project. Where
		a schematic has been redrawn in KiCad for Akashic, or the designer shares theirs under an open license, it is shown, and a
		redrawn one can be downloaded as a <span class="mono">.kicad_sch</span> fragment to drop into your own project.
	</p>
</section>

<section>
	<h2 class="label strong">The parts list</h2>
	<p>The list is grouped by kind of part, with five columns:</p>
	<dl class="terms">
		<div><dt class="label">Ref</dt><dd>The designator on the board. Sources that list parts without designators show a count instead, such as <span class="mono">×2</span>.</dd></div>
		<div><dt class="label">Value</dt><dd>As the source wrote it.</dd></div>
		<div><dt class="label">Normalized</dt><dd>The same value written one way. A part named by number (an IC, a transistor, a diode, a pot) links to its page and every other circuit that uses it.</dd></div>
		<div><dt class="label">Type</dt><dd>The source's description: film capacitor, DIP-8, log pot.</dd></div>
		<div><dt class="label">Notes</dt><dd>The source's notes, such as a substitute it suggests or a socket it recommends.</dd></div>
	</dl>

	<h3>How far to trust a value</h3>
	<p>
		Most parts lists are read from the text of the build document or from a KiCad interactive BOM, and are exact. Some documents only
		have a picture of the table or the schematic, and those values are read by machine and marked:
	</p>
	<dl class="terms">
		<div><dt><span class="src">ocr</span></dt><dd>read from an image of the parts list</dd></div>
		<div><dt><span class="src">sch</span></dt><dd>paired from the labels on the schematic drawing</dd></div>
		<div><dt><span class="src fixed">fixed</span></dt><dd>corrected by hand, where the source had a typo or the machine read it wrong</dd></div>
	</dl>
	<p>
		Check any marked value against the build document before you order. A box headed <em>Check before you build</em> lists the
		values the reader was not sure of, as on <a href="{base}/circuit/bentfishbowl-clearglass-some-new-glass-for-your-bass">Bent Fishbowl's Clearglass</a>.
		Where a blog post corrects its own schematic, the corrections are applied to the list and listed above it as <em>Fixes to the
		schematic</em>.
	</p>
	<p>
		A layout often names only its active parts and pots in the legend, with the resistor and capacitor values printed on the drawing;
		its page says so when that is all the list has. If a circuit has no parts list at all, the page says why and where to find one.
	</p>

	<h3>Variants</h3>
	<p>
		When a build document gives values for several versions of the circuit, a <em>Variant</em> row of buttons switches the list
		between them. The Muffin Fuzz has eight, one for each Big Muff it can build. Searches and part counts use the first variant.
	</p>

	<h3>Copy it, or report it</h3>
	<ul>
		<li><em>Copy as TSV</em> copies the list shown, variant included, as tab-separated text that pastes straight into a spreadsheet or a parts order.</li>
		<li><em>Report a wrong parse</em> opens a GitHub issue with the circuit's name and address filled in. Say which row is wrong and what the build document says; the fix stays through every weekly refresh.</li>
	</ul>
</section>

<section>
	<h2 class="label strong">Other boards of the same pedal</h2>
	<p>
		At the bottom, every other board, layout and schematic based on the same original, with its vendor, box and price, so you can
		compare enclosures, prices and parts without searching again.
	</p>
</section>
