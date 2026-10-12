<script lang="ts">
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import type { Snippet } from 'svelte';
	import { MAKER_NAME } from '$lib/site';

	let { children }: { children: Snippet } = $props();
	const pages = [
		{ href: `${base}/workbench`, label: 'Overview' },
		{ href: `${base}/workbench/sourcing`, label: 'Sourcing' },
		{ href: `${base}/workbench/building`, label: 'Building' },
		{ href: `${base}/workbench/links`, label: 'Links' }
	];
	const here = $derived(page.url.pathname.replace(/\/$/, ''));
</script>

<div class="workbench">
	<nav class="sub" aria-label="Workbench">
		<span class="label strong">Workbench</span>
		{#each pages as p}
			<a class="label" href={p.href} aria-current={here === p.href ? 'page' : undefined}>{p.label}</a>
		{/each}
	</nav>
	{@render children()}
	<p class="voice dim">The Workbench is one builder's notes, from {MAKER_NAME}: what I buy, where and why. The rest of Akashic is reference; this part is opinion.</p>
</div>

<style>
	.workbench { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.sub { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; padding-bottom: 10px; margin-bottom: 20px; border-bottom: 1px solid var(--rule-strong); }
	.sub a[aria-current='page'] { color: var(--ink); box-shadow: 0 2px 0 var(--coat); }
	.voice { margin: 36px 0 0; padding-top: 12px; border-top: 1px solid var(--rule); max-width: 78ch; }
	.dim { color: var(--ink-3); }
	.workbench :global(h1) { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.workbench :global(.lede) { color: var(--ink-2); margin: 0 0 18px; max-width: 78ch; }
	.workbench :global(section) { margin-top: 28px; }
	.workbench :global(section h2) { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 10px; }
	.workbench :global(section h3) { font-size: 17px; margin: 16px 0 4px; }
	.workbench :global(section p) { margin: 0 0 10px; max-width: 78ch; }
	.workbench :global(section ul), .workbench :global(section ol) { margin: 0 0 10px; padding-left: 20px; max-width: 78ch; }
	.workbench :global(section li) { margin-bottom: 4px; }
	.workbench :global(section a), .workbench :global(.lede a) { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.workbench :global(section a:hover), .workbench :global(.lede a:hover) { text-decoration-color: var(--coat); }
	.workbench :global(.more) { color: var(--ink-3); font-size: 14px; }
</style>
