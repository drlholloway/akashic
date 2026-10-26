<script lang="ts">
	import { base } from '$app/paths';
	import Faceplate from '$lib/Faceplate.svelte';
</script>

<svelte:head>
	<title>Searching and filtering · Guide · Akashic</title>
	<meta name="description" content="What Akashic's search box matches, how the filters combine, sorting, and sharing a search as a link." />
</svelte:head>

<header class="head">
	<h1>Searching and filtering</h1>
	<p class="lede">
		The <a href="{base}/">Circuits</a> page is the whole library in one table. The search box narrows it by what you type, the filters
		on the left narrow it further, and the address bar keeps both, so any list you build can be bookmarked or sent to someone.
	</p>
</header>

<section>
	<h2 class="label strong">The search box</h2>
	<p>One box searches everything at once:</p>
	<ul>
		<li>the circuit's name and subtitle,</li>
		<li>the pedal it is based on,</li>
		<li>its category and effect type, its vendor and its enclosure,</li>
		<li>the active parts in its parts list: ICs, transistors, diodes, optocouplers,</li>
		<li>its tags and the names of its controls.</li>
	</ul>
	<p>A few rules make it behave:</p>
	<ul>
		<li><strong>Every word must match.</strong> <a href="{base}/?q=phaser%20125B">phaser 125B</a> lists phasers that fit a 125B, not every phaser and every 125B board.</li>
		<li><strong>Words match from the start.</strong> <span class="mono">muf</span> finds Muff and <span class="mono">trem</span> finds Tremolo, so you can stop typing early.</li>
		<li><strong>Small typos are forgiven</strong> in words longer than four letters: <span class="mono">tremelo</span> still finds tremolos. Short words and part numbers must be exact.</li>
		<li><strong>Control names match whole words only</strong>, so <span class="mono">rat</span> finds the Rat and not every circuit with a Rate knob.</li>
		<li><strong>The best match comes first.</strong> A word in the circuit's name counts most, then the pedal it is based on, then its parts.</li>
	</ul>
	<table class="sheet-table try">
		<thead><tr><th>Try</th><th>Finds</th></tr></thead>
		<tbody>
			<tr><td><a class="mono" href="{base}/?q=big%20muff">big muff</a></td><td>Boards named after or based on a Big Muff.</td></tr>
			<tr><td><a class="mono" href="{base}/?q=PT2399">PT2399</a></td><td>Circuits built around one chip: here, the delay chip in most DIY delays.</td></tr>
			<tr><td><a class="mono" href="{base}/?q=2N5088%20fuzz">2N5088 fuzz</a></td><td>Fuzzes that use a 2N5088.</td></tr>
			<tr><td><a class="mono" href="{base}/?q=blend">blend</a></td><td>Circuits with a Blend knob, as well as any named Blend.</td></tr>
			<tr><td><a class="mono" href="{base}/?q=aion%20chorus">aion chorus</a></td><td>One vendor's choruses.</td></tr>
		</tbody>
	</table>
	<p>While a search is on, the list is ranked by match and the Sort menu is off. Clear the search to sort by name, vendor, price or the size of the parts list.</p>
</section>

<section>
	<h2 class="label strong">Filters</h2>
	<p>The column on the left (above the list on a narrow screen) filters the list. Each choice is a chip; press it again to turn it off.</p>
	<dl class="terms">
		<div><dt class="label">My bench</dt><dd>Only the circuits you have kept. See <a href="{base}/guide/workbench">My bench</a>.</dd></div>
		<div><dt class="label">Build</dt><dd>PCB, Vero, Perfboard, Tagboard, Turret board, Point to point. <em>Verified layouts</em> keeps layouts their source marks as built and working.</dd></div>
		<div><dt class="label">Vendor</dt><dd>The source of the circuit.</dd></div>
		<div><dt class="label">Category</dt><dd>Overdrive, Fuzz, Delay, Utility and the rest.</dd></div>
		<div><dt class="label">Enclosure</dt><dd>The eight most common box sizes in the current list.</dd></div>
		<div><dt class="label">Knobs</dt><dd>How many controls the circuit has.</dd></div>
		<div><dt class="label">Controls</dt><dd>Named controls such as Bias, Blend or Presence; <em>More</em> shows the full set. Spellings are grouped, so Vol, Level and Output count as Volume.</dd></div>
		<div><dt class="label">In stock only</dt><dd>Drops boards the vendor shows as out of stock or no longer lists.</dd></div>
	</dl>
	<p>How they combine:</p>
	<ul>
		<li>Two chips in the same group mean <em>either</em>: Fuzz and Overdrive lists both.</li>
		<li>Chips in different groups mean <em>both</em>: Fuzz and 1590B lists fuzzes in a 1590B.</li>
		<li>Controls are the exception: choose Bias and Blend and every circuit listed has both.</li>
		<li>The number on a chip is how many circuits you would see if you chose it, given everything else that is on.</li>
	</ul>
	<p>
		Above the table, the chips you have applied are listed with a × to remove each, and <em>Clear all</em> starts over. Clicking an
		original in the Based on column filters to every circuit based on it. <em>Collapse all</em> folds the filter groups out of the way.
	</p>
</section>

<section>
	<h2 class="label strong">Reading the table</h2>
	<div class="glyphs">
		<Faceplate enclosure="1590B" controls={['Filter', 'Distortion', 'Sweep', 'Volume']} size={30} title="A 1590B with four knobs" />
		<Faceplate enclosure="125B" controls={['Volume', 'Gain', 'Tone']} size={30} title="A 125B with three knobs" />
		<Faceplate enclosure="1590BB" controls={['Rate', 'Depth', 'Mix', 'Feedback', 'Delay', 'Volume']} size={30} title="A 1590BB with six knobs" />
	</div>
	<p>
		The small drawing at the start of each row is the circuit's faceplate: the enclosure at its real proportions, with the knobs laid
		out the way you would drill them, the LED and the footswitch. A gray box means the controls are not known. Above, a 1590B with four
		knobs, a 125B with three and a 1590BB with six.
	</p>
	<dl class="terms">
		<div><dt class="label">Circuit</dt><dd>The name, linking to its page, with tags: the build if it is not a PCB (with the board size of a layout), <em>Bench</em> if you have kept it, <em>Verified</em> or <em>Unverified</em> for a layout, and the first few active parts.</dd></div>
		<div><dt class="label">Based on</dt><dd>The original; click it to list every circuit based on it. Gray text is the source's own wording where it names no pedal Akashic knows, and a dash means it names none, usually because the design is its own.</dd></div>
		<div><dt class="label">Box</dt><dd>The enclosure; a dash where the source does not say.</dd></div>
		<div><dt class="label">Price</dt><dd>The vendor's list price in the currency you choose, marked when out of stock. Free layouts and schematics have none.</dd></div>
		<div><dt class="label">BOM</dt><dd>How many rows its parts list has; a dash means no parts list could be read.</dd></div>
	</dl>
	<p>
		The <em>Prices</em> menu shows every price in dollars, euros or pounds, converted at the European Central Bank's rates, or
		<em>As listed</em> in the vendor's own currency. Your choice is remembered in this browser.
	</p>
</section>

<section>
	<h2 class="label strong">Share or bookmark a search</h2>
	<p>
		Every search and filter is in the page's address, so copying it copies the list. For example,
		<a href="{base}/?cat=Fuzz&enc=1590A&stock=1">fuzzes in a 1590A that are in stock</a>. The parts of the address, if you want to write
		one by hand:
	</p>
	<table class="sheet-table try">
		<thead><tr><th>Key</th><th>Means</th></tr></thead>
		<tbody>
			<tr><td class="mono">q=</td><td>the search words</td></tr>
			<tr><td class="mono">based=</td><td>an original, as spelled on the <a href="{base}/originals">Originals</a> page</td></tr>
			<tr><td class="mono">part=</td><td>an active part, such as <a class="mono" href="{base}/?part=LM308">LM308</a></td></tr>
			<tr><td class="mono">cat= enc= vendor= build= ctl=</td><td>category, enclosure, vendor, build and control filters; separate several with commas</td></tr>
			<tr><td class="mono">knobs=</td><td>a knob count</td></tr>
			<tr><td class="mono">stock=1 verified=1 bench=1</td><td>in stock only, verified layouts only, my bench only</td></tr>
		</tbody>
	</table>
</section>

<style>
	.glyphs { display: flex; gap: 12px; align-items: flex-end; margin: 4px 0 10px; }
</style>
