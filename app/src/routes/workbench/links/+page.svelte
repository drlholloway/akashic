<script lang="ts">
	type Link = { name: string; href: string; note: string };
	const groups: { title: string; links: Link[] }[] = [
		{
			title: 'Learn',
			links: [
				{ name: 'The Art of Electronics, 3rd edition', href: 'https://www.amazon.com/Art-Electronics-Paul-Horowitz/dp/0521809266', note: 'Horowitz and Hill: the electronics textbook.' },
				{ name: "Wampler's Guitar Pedal Course", href: 'https://www.guitarpedalcourse.com/', note: 'A paid course on how pedal circuits work.' },
				{ name: 'Electrosmash', href: 'https://web.archive.org/web/2026/https://www.electrosmash.com/', note: 'Stage-by-stage analyses of classic pedal circuits. The site was not answering when this was written, so the link goes to an archived copy.' },
				{ name: 'GEOFEX', href: 'http://www.geofex.com/', note: "R.G. Keen's articles: the technology of the Fuzz Face, the Tube Screamer and much more." },
				{ name: 'AMZ (muzique.com)', href: 'https://www.muzique.com/', note: "Jack Orman's lab notebook and articles." }
			]
		},
		{
			title: 'Ask',
			links: [
				{ name: 'DIY Stompboxes', href: 'https://www.diystompboxes.com/', note: 'The long-running forum.' },
				{ name: 'PedalPCB Forum', href: 'https://forum.pedalpcb.com', note: 'Build reports and troubleshooting, for more than PedalPCB boards.' },
				{ name: 'r/diypedals', href: 'https://www.reddit.com/r/diypedals', note: 'Reddit.' }
			]
		},
		{
			title: 'Tools and lookups',
			links: [
				{ name: 'Resistor color code decoder', href: 'https://circuitdigest.com/calculators/5-band-resistor-color-code-calculator', note: 'For 5-band resistors.' },
				{ name: 'Semiconductor company logos', href: 'https://reference.huntingtonaudio.com/semiconductor-logos', note: 'Who made the chip, from the logo printed on it.' },
				{ name: 'What Can I Build?', href: 'https://dvhx.github.io/what-can-i-build/', note: 'Enter the parts you have and see which circuits they cover.' }
			]
		},
		{
			title: 'Making your own boards',
			links: [
				{ name: 'JLCPCB assembly guide', href: 'https://github.com/z2amiller/pedalfx/blob/main/docs/JLCPCBA.md', note: "z2amiller's notes on ordering assembled pedal boards." },
				{ name: 'JLCPCB component catalog', href: 'https://yaqwsx.github.io/jlcparts/', note: 'A searchable catalog of the parts JLCPCB can place.' }
			]
		},
		{
			title: 'More lists',
			links: [
				{ name: 'Awesome Pedal', href: 'https://github.com/szukalski/awesome-pedal', note: 'A long curated list of pedal-building resources.' },
				{ name: 'My guitar effects layouts', href: 'https://github.com/drlholloway/guitar-effects-layouts', note: 'Layouts I have drawn.' }
			]
		}
	];
</script>

<svelte:head>
	<title>Links · Workbench · Akashic</title>
	<meta name="description" content="Helpful sites and tools for building guitar pedals: books and courses, forums, calculators and lookups, and guides for having your own boards made." />
</svelte:head>

<header class="head">
	<h1>Links</h1>
	<p class="lede">Books, sites and tools with a lot of knowledge in them, or one thing I keep needing to look up.</p>
</header>

{#each groups as g}
	<section>
		<h2 class="label strong">{g.title}</h2>
		<dl class="links">
			{#each g.links as l}
				<div><dt><a href={l.href} target="_blank" rel="noopener">{l.name}</a></dt><dd>{l.note}</dd></div>
			{/each}
		</dl>
	</section>
{/each}

<style>
	.links { margin: 0; display: grid; gap: 6px; }
	.links div { display: grid; grid-template-columns: minmax(0, 32ch) 1fr; gap: 4px 20px; align-items: baseline; }
	.links dt, .links dd { margin: 0; }
	.links dt { font-weight: 600; }
	.links dd { color: var(--ink-2); }
	@media (max-width: 700px) { .links div { grid-template-columns: 1fr; margin-bottom: 6px; } }
</style>
