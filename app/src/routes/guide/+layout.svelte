<script lang="ts">
	import { page } from '$app/state';
	import { base } from '$app/paths';
	import type { Snippet } from 'svelte';
	import { ISSUES_URL } from '$lib/site';

	let { children }: { children: Snippet } = $props();
	const pages = [
		{ href: `${base}/guide`, label: 'Start here' },
		{ href: `${base}/guide/search`, label: 'Searching' },
		{ href: `${base}/guide/circuit`, label: 'A circuit page' },
		{ href: `${base}/guide/parts`, label: 'Originals and parts' },
		{ href: `${base}/guide/workbench`, label: 'Bench and build' },
		{ href: `${base}/guide/questions`, label: 'Questions' }
	];
	const here = $derived(page.url.pathname.replace(/\/$/, ''));
	const at = $derived(pages.findIndex((p) => p.href === here));
	const next = $derived(at >= 0 ? pages[at + 1] : undefined);
</script>

<div class="guide">
	<nav class="sub" aria-label="Guide">
		<span class="label strong">Guide</span>
		{#each pages as p}
			<a class="label" href={p.href} aria-current={here === p.href ? 'page' : undefined}>{p.label}</a>
		{/each}
	</nav>
	{@render children()}
	<p class="foot dim">
		{#if next}Next: <a href={next.href}>{next.label}</a>. {/if}Something here wrong or missing? <a href={ISSUES_URL} target="_blank" rel="noopener">Open an issue</a>.
	</p>
</div>

<style>
	.guide { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.sub { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 20px; padding-bottom: 10px; margin-bottom: 20px; border-bottom: 1px solid var(--rule-strong); }
	.sub a[aria-current='page'] { color: var(--ink); box-shadow: 0 2px 0 var(--coat); }
	@media (max-width: 480px) { .sub .strong { display: none; } } /* the header already marks the section */
	.foot { margin: 36px 0 0; padding-top: 12px; border-top: 1px solid var(--rule); max-width: 78ch; }
	.foot a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.dim { color: var(--ink-3); }
	.guide :global(h1) { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.guide :global(.lede) { color: var(--ink-2); margin: 0 0 18px; max-width: 78ch; }
	.guide :global(section) { margin-top: 28px; }
	.guide :global(section h2) { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 10px; }
	.guide :global(section h3) { font-size: 17px; margin: 16px 0 4px; }
	.guide :global(section p) { margin: 0 0 10px; max-width: 78ch; }
	.guide :global(section ul), .guide :global(section ol) { margin: 0 0 10px; padding-left: 20px; max-width: 78ch; }
	.guide :global(section li) { margin-bottom: 4px; }
	.guide :global(section a), .guide :global(.lede a) { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.guide :global(section a:hover), .guide :global(.lede a:hover) { text-decoration-color: var(--coat); }
	.guide :global(.try) { max-width: 78ch; margin-bottom: 10px; }
	.guide :global(.try td:first-child) { white-space: nowrap; }
	.guide :global(dl.terms) { display: grid; gap: 8px; margin: 0 0 10px; max-width: 78ch; }
	.guide :global(dl.terms div) { display: grid; grid-template-columns: 16ch 1fr; gap: 12px; align-items: baseline; }
	.guide :global(dl.terms dt), .guide :global(dl.terms dd) { margin: 0; }
	@media (max-width: 560px) { .guide :global(dl.terms div) { grid-template-columns: 1fr; gap: 0; } }
	.guide :global(.src) { padding: 0 4px; border: 1px solid var(--rule-strong); border-radius: 3px; font-family: var(--label); font-weight: 600; font-size: 10px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--ink-3); }
	.guide :global(.src.fixed) { border-color: var(--coat); color: var(--coat); }
</style>
