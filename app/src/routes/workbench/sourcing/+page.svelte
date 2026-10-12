<script lang="ts">
	import { base } from '$app/paths';

	const AION_GUIDE = 'https://aionfx.com/resources/parts-sourcing-where-to-buy-what/';
	const TAYDA = 'https://www.taydaelectronics.com';
	const MOUSER = 'https://www.mouser.com';
	const LMS = 'https://lovemyswitches.com/';
	const SBP = 'https://stompboxparts.com/';
	const AION = 'https://aionfx.com';
	const SMALLBEAR = 'https://smallbear-electronics.mybigcommerce.com/';
	const CABINTECH = 'https://cabintechglobal.com/';
	const SBS = 'https://www.stompboxsupply.com/';
	const WIRE = 'https://smallbear-electronics.mybigcommerce.com/22-pre-bond-colors-50-ft-spool/';
</script>

{#snippet x(href: string, text: string)}<a {href} target="_blank" rel="noopener">{text}</a>{/snippet}
{#snippet parts(key: string, text: string)}<p class="more"><a href="{base}/parts#sec-{key}">{text}</a></p>{/snippet}

<svelte:head>
	<title>Sourcing · Workbench · Akashic</title>
	<meta name="description" content="Where to buy pedal parts and which brands to stick to: resistors, capacitors, pots, semiconductors, enclosures, jacks, switches and wire." />
</svelte:head>

<header class="head">
	<h1>Sourcing</h1>
	<p class="lede">
		Where to buy components can start a holy war, so this is just where I buy and what I get from each place. Read it as my
		take on {@render x(AION_GUIDE, "AionFX's parts sourcing guide")}, which is the better starting point.
	</p>
</header>

<section>
	<h2 class="label strong">Which shop for what</h2>
	<ul>
		<li>{@render x(TAYDA, 'Tayda Electronics')}: passive components (resistors, potentiometers and the like), enclosures, occasionally ICs.</li>
		<li>{@render x(MOUSER, 'Mouser')}: capacitors, ICs, occasionally resistors or other passives, audio jacks and DC jacks.</li>
		<li>{@render x(LMS, 'Love My Switches')}: knobs and enclosures.</li>
		<li>{@render x(SBP, 'Stomp Box Parts')}: rare diodes, footswitches, occasionally audio jacks, knobs and enclosures.</li>
		<li>{@render x(AION, 'AionFX')}: the J201 (surface-mount, on an adapter for through-hole) and other parts specific to AionFX builds.</li>
		<li>{@render x(SMALLBEAR, 'Small Bear Electronics')}: wire, PCBs, hard-to-find ICs and transistors.</li>
		<li>{@render x(CABINTECH, 'Cabintech Global')}: the best price for Xvive vactrols (VTL5C1, VTL5C3, VTL5C4).</li>
	</ul>
	<p>
		On quality: I have not had a problem with anything from Tayda, Mouser or anywhere else, but I try to keep to certain
		brands, named below.
	</p>
</section>

<section>
	<h2 class="label strong">Resistors</h2>
	<p>
		1/4W 1% metal film is my default on everything, even boards that ask for 1/8W. The Royal Ohm ones from Tayda are very
		nice and have thick leads. KOA Speer and Yageo from Mouser are both good. Buy in bulk: they get cheaper and you build up
		an inventory. I buy 100 or 200 of a value each time, which is a good balance.
	</p>
</section>

<section>
	<h2 class="label strong">Capacitors</h2>
	<p>
		Through-hole capacitors come in four kinds you will meet in pedals: MLCC, film, tantalum and electrolytic.
		{@render x(AION_GUIDE, "AionFX's guide")} is spot on for what to buy, and I follow it. Mouser has good prices in the US,
		and Tayda now carries the name brands (WIMA, Panasonic) too.
	</p>
	<h3>MLCC</h3>
	<p>
		For the pF values and anything under 1nF. Stick to <span class="mono">C0G</span> and <span class="mono">NP0</span>:
		they are the highest quality, with the tightest tolerance. <span class="mono">Z5U</span>, <span class="mono">X5R</span> and
		<span class="mono">X7R</span> drift more with temperature and voltage. AionFX recommends the TDK FG28 series, and I use it
		whenever I can; I have used all types and not noticed much difference.
	</p>
	<h3>Film</h3>
	<p>
		For 1nF up to 2.2µF. WIMA and the Kemet PHE426 series are the ones to look for, and they are reasonable in bulk. I have
		used generic ones from Mouser and not heard much difference, but I do love the bright red WIMA caps.
	</p>
	<h3>Tantalum</h3>
	<p>Not many effects use them, but you will see them now and then. Get them from Tayda.</p>
	<h3>Electrolytic</h3>
	<p>
		From about 1µF upward. On a schematic or a PCB they are the round ones with the positive and negative terminals marked.
		You cannot go wrong with Panasonic, Nichicon, Rubycon or Lelon; I usually buy Panasonic or Nichicon and have used Tayda's
		with no trouble. Most boards are laid out for standard diameters:
	</p>
	<ul>
		<li>1µF to 47µF: 5mm</li>
		<li>100µF to 220µF: 6.3mm</li>
	</ul>
</section>

<section>
	<h2 class="label strong">Potentiometers</h2>
	<p>
		Tayda and Stomp Box Parts both have wonderful pots. I like Stomp Box Parts' Cusack brand a shade more than the Alpha or
		Tayda ones, but most of my builds use Alpha or Tayda and the difference is basically imperceptible. If you buy Tayda's
		16mm pots, get the 6.35mm shafts. I generally avoid splined and D shafts.
	</p>
	{@render parts('POT', 'Every pot value in the library, by taper')}
</section>

<section>
	<h2 class="label strong">Diodes and LEDs</h2>
	<p>
		Tayda for basically everything. For germanium or Russian diodes, Stomp Box Parts is very good; eBay works too, but be
		careful, there are some shady sellers.
	</p>
	{@render parts('D', 'Every diode in the library')}
</section>

<section>
	<h2 class="label strong">Transistors</h2>
	<p>
		Mouser or Tayda; I have not had a bad one from either. Mouser is probably a little safer, and I have found better deals
		there than at Tayda, so check both if you are watching cost. For germanium or Soviet transistors, eBay has a few
		trustworthy sellers, or try Stomp Box Parts.
	</p>
	{@render parts('Q', 'Every transistor in the library, with datasheets and substitutes')}
</section>

<section>
	<h2 class="label strong">ICs</h2>
	<p>For anything still in production, Tayda or Mouser. After that, Stomp Box Parts or Small Bear Electronics.</p>
	{@render parts('IC', 'Every IC in the library, with datasheets')}
</section>

<section>
	<h2 class="label strong">Enclosures</h2>
	<p>
		Tayda has a great selection at very reasonable prices, and it is my standard for anything personal. Stomp Box Parts, Love
		My Switches, {@render x(SBS, 'Stomp Box Supply')} and sometimes Mouser have them too. For anything I am going to sell, I
		make sure it is a Hammond or Gorva enclosure.
	</p>
</section>

<section>
	<h2 class="label strong">Knobs</h2>
	<p>Love My Switches or Tayda. I really like the smaller aluminum knobs Love My Switches sells, and Tayda has some great choices.</p>
</section>

<section>
	<h2 class="label strong">Switches and footswitches</h2>
	<p>
		Tayda has almost every switch you will need (SPST, SPDT, DPDT and so on) and a good range of rotary switches. If Tayda
		does not have it, I look at Love My Switches or Stomp Box Parts. Small Bear Electronics carries many as well.
	</p>
	{@render parts('SW', 'Every switch type in the library')}
</section>

<section>
	<h2 class="label strong">Jacks</h2>
	<h3>1/4" audio</h3>
	<p>Tayda by default, then Mouser, Stomp Box Parts and Small Bear. Love My Switches is good too.</p>
	<h3>DC</h3>
	<p>
		Tayda, Mouser or Stomp Box Parts for almost all of them. Small Bear has a very slim one that is great for tight builds.
		For my own pedals I like the ones that fix from the outside: they leave more room in the box, and everything comes out
		easily when something needs testing.
	</p>
</section>

<section>
	<h2 class="label strong">Wire</h2>
	<p>I follow AionFX here too: {@render x(WIRE, 'the 22 AWG pre-bond wire')} from Small Bear Electronics.</p>
</section>

<style>
	.mono { font-family: var(--mono); font-size: 13px; }
</style>
