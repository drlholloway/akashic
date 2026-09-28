<script lang="ts">
	import { REPO_URL } from '$lib/site';

	let { data } = $props();
	const total = $derived(data.weeks.reduce((n, w) => n + w.items.length, 0));
	const day = (iso: string, opts: Intl.DateTimeFormatOptions) => new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-US', { timeZone: 'UTC', ...opts });
	const weekLabel = (monday: string) => {
		const end = new Date(`${monday}T12:00:00Z`);
		end.setUTCDate(end.getUTCDate() + 6);
		return `${day(monday, { month: 'short', day: 'numeric' })} – ${day(end.toISOString().slice(0, 10), { month: 'short', day: 'numeric', year: 'numeric' })}`;
	};
</script>

<svelte:head><title>Changelog · Akashic</title></svelte:head>

<div class="changes">
	<header class="head">
		<h1>Changelog</h1>
		<p class="lede">
			What changed in the library each week: sources added, parsing fixes and changes to the site. {total} changes so far. The code
			and the full history are on <a href={REPO_URL} target="_blank" rel="noopener">GitHub</a>.
		</p>
	</header>
	{#each data.weeks as w (w.week)}
		<section>
			<h2 class="label strong">Week of {weekLabel(w.week)} <span class="mono dim">{w.items.length}</span></h2>
			<ul>
				{#each w.items as c (c.sha)}
					<li>
						<span class="mono date">{day(c.date, { weekday: 'short', month: 'short', day: 'numeric' })}</span>
						<div class="body">
							{#if c.detail}
								<details>
									<summary>{c.subject}</summary>
									<p>{c.detail}</p>
									<a class="mono sha" href="{REPO_URL}/commit/{c.sha}" target="_blank" rel="noopener">{c.sha}</a>
								</details>
							{:else}
								<p class="subject">{c.subject} <a class="mono sha" href="{REPO_URL}/commit/{c.sha}" target="_blank" rel="noopener">{c.sha}</a></p>
							{/if}
						</div>
					</li>
				{/each}
			</ul>
		</section>
	{/each}
</div>

<style>
	.changes { padding: 24px var(--gutter) 48px; max-width: 900px; }
	.head h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.lede { max-width: 70ch; color: var(--ink-2); margin-bottom: 8px; }
	.lede a { text-decoration: underline; text-underline-offset: 2px; }
	section { margin-top: 28px; }
	section h2 { padding-bottom: 6px; border-bottom: 1px solid var(--rule-strong); margin-bottom: 4px; }
	.dim { color: var(--ink-3); }
	ul { list-style: none; margin: 0; padding: 0; }
	li { display: grid; grid-template-columns: 96px minmax(0, 1fr); gap: 4px 16px; padding: 8px 0; border-bottom: 1px solid var(--rule); }
	.date { color: var(--ink-3); font-size: 12px; padding-top: 3px; white-space: nowrap; }
	summary { cursor: pointer; list-style-position: outside; }
	summary:hover { color: var(--coat); }
	details p { margin: 6px 0 4px; color: var(--ink-2); max-width: 70ch; }
	.subject { margin: 0; }
	.sha { font-size: 12px; color: var(--ink-3); }
	.sha:hover { color: var(--ink); }
	@media (max-width: 560px) {
		li { grid-template-columns: 1fr; }
	}
</style>
