<script lang="ts">
	/**
	 * A faceplate glyph drawn from real data: enclosure size sets the outline's
	 * proportions, the controls list sets the knob count and their labels.
	 * The same drawing serves at 28px (index row) and 260px (circuit header).
	 */
	interface Props {
		enclosure?: string;
		controls?: string[];
		size?: number; // rendered height in px
		labels?: boolean; // print control names (only sensible when large)
		title?: string;
	}
	let { enclosure = '', controls = [], size = 28, labels = false, title = '' }: Props = $props();

	// Hammond footprints in mm (width x height), portrait orientation.
	const FOOTPRINTS: Record<string, [number, number]> = {
		'1590A': [39, 93],
		'1590B': [60, 112],
		'1590B2': [60, 112],
		'1590N1': [66, 121],
		'125B': [66, 121],
		'1590BB': [94, 119],
		'1590BB2': [94, 119],
		'1590XX': [145, 121],
		'1590DD': [188, 120],
		'1590LB': [51, 51],
		'1032L': [140, 130],
		'1550B': [60, 112],
		'1590C': [94, 120],
		'1590Q': [94, 120],
		'1590BS': [60, 112],
		'1590BBS': [94, 119],
		'1590D': [188, 120],
		'1590E': [188, 120],
		'1590P1': [153, 82],
		'1590R1': [192, 111],
		'1590S': [111, 82],
		'1590T': [120, 80],
		'1590X': [145, 121],
		'1590Y': [92, 92],
		'1590Z': [120, 100],
		'1590A2': [39, 93],
		'1590J': [145, 95],
		'1590G': [100, 50]
	};

	const knobs = $derived.by(() => {
		const single = controls.length === 1 && /^(\d+) knobs?$/.exec(controls[0]);
		if (single) return Array.from({ length: Number(single[1]) }, (_, i) => `${i + 1}`);
		return controls.filter((c) => !/^\d+ knobs?$/.test(c));
	});
	const known = $derived(controls.length > 0);
	const fp = $derived(FOOTPRINTS[enclosure] ?? [60, 112]);
	const W = $derived(fp[0]);
	const H = $derived(fp[1]);

	// Rows of knobs, top to bottom, the way builders drill them.
	function rows(n: number): number[] {
		if (n <= 0) return [];
		if (n <= 3) return [n];
		if (n === 4) return [2, 2];
		if (n === 5) return [3, 2];
		if (n === 6) return [3, 3];
		if (n === 7) return [4, 3];
		if (n === 8) return [4, 4];
		const out: number[] = [];
		let left = n;
		while (left > 0) {
			const take = Math.min(4, left);
			out.push(take);
			left -= take;
		}
		return out;
	}
	const layout = $derived.by(() => {
		const r = rows(knobs.length);
		const pts: { x: number; y: number; label: string }[] = [];
		const top = H * 0.16;
		const bottomReserved = H * 0.42; // LED + footswitch zone
		const usable = H - top - bottomReserved;
		const rowGap = r.length > 1 ? usable / (r.length - 1) : 0;
		let i = 0;
		r.forEach((count, ri) => {
			const y = r.length === 1 ? top + usable * 0.25 : top + rowGap * ri;
			const cell = W / count;
			for (let c = 0; c < count; c++) {
				pts.push({ x: cell * (c + 0.5), y, label: knobs[i++] ?? '' });
			}
		});
		return pts;
	});
	const knobR = $derived(Math.min(W / (Math.max(...rows(knobs.length), 1) * 2.6), H * 0.075));
	const scale = $derived(size / H);
	const cellW = $derived(W / Math.max(...rows(knobs.length), 1));
	// Screen-print labels must fit their knob's cell: scale by the longest label in the row.
	const longest = $derived(Math.max(4, ...knobs.map((k) => k.length)));
	const fontPx = $derived(Math.max(4.2, Math.min(knobR * 0.85, (cellW * 0.92) / (longest * 0.56))));
</script>

<svg
	width={W * scale}
	height={size}
	viewBox="0 0 {W} {H}"
	role="img"
	aria-label={title || `${enclosure || 'enclosure'} with ${knobs.length} controls`}
	class="faceplate"
	class:unknown={!known}
	style="--sc: {1 / scale}"
>
	<rect x="0.6" y="0.6" width={W - 1.2} height={H - 1.2} rx={W * 0.06} class="shell" />
	{#if known}
		{#each layout as k}
			<circle cx={k.x} cy={k.y} r={knobR} class="knob" />
			<line x1={k.x} y1={k.y} x2={k.x} y2={k.y - knobR * 0.78} class="pointer" />
			{#if labels && k.label}
				<text x={k.x} y={k.y + knobR + fontPx * 1.15} text-anchor="middle" font-size={fontPx} class="print">{k.label.toUpperCase()}</text>
			{/if}
		{/each}
		<circle cx={W / 2} cy={H * 0.66} r={Math.max(1.4, W * 0.028)} class="led" />
		<circle cx={W / 2} cy={H * 0.84} r={Math.min(W * 0.11, H * 0.07)} class="switch" />
	{:else}
		<line x1={W * 0.25} y1={H * 0.5} x2={W * 0.75} y2={H * 0.5} class="pointer" />
	{/if}
</svg>

<style>
	.faceplate { display: block; flex: none; overflow: visible; }
	.shell { fill: var(--coat); stroke: var(--coat-2); stroke-width: calc(1px * var(--sc)); }
	.unknown .shell { fill: var(--sheet-3); stroke: var(--rule-strong); }
	.knob { fill: none; stroke: var(--coat-ink); stroke-width: calc(1.2px * var(--sc)); }
	.pointer { stroke: var(--coat-ink); stroke-width: calc(1.2px * var(--sc)); stroke-linecap: round; }
	.unknown .pointer { stroke: var(--rule-strong); }
	.led { fill: var(--coat-ink); }
	.switch { fill: none; stroke: var(--coat-ink); stroke-width: calc(1.2px * var(--sc)); }
	.print { fill: var(--coat-ink); font-family: var(--label); font-weight: 600; letter-spacing: 0.06em; }
</style>
