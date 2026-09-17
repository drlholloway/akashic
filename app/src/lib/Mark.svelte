<script lang="ts">
	/** The Akashic mark: an eye whose iris is a knob, drawn in the app's own tokens. */
	let { size = 28, title = 'Akashic' }: { size?: number; title?: string } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 64 64" role="img" aria-label={title} class="mark">
	<rect width="64" height="64" rx="14" class="coat" />
	<g fill="none" class="ink" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round">
		<path d="M7 32 C 17 17, 47 17, 57 32 C 47 47, 17 47, 7 32 Z" />
		<circle cx="32" cy="32" r="10.5" />
		<line x1="32" y1="33" x2="32" y2="24" />
	</g>
</svg>

<style>
	.mark { display: block; flex: none; }
	.coat { fill: var(--coat); }
	.ink { stroke: var(--coat-ink); }
</style>
