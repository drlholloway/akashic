<script lang="ts">
	import { base } from '$app/paths';
	import CircuitTable from '$lib/CircuitTable.svelte';
	import { PART_CATEGORY_NAMES } from '$lib/types';
	let { data } = $props();
</script>

<svelte:head><title>{data.part.value} · circuits using it · Akashic</title></svelte:head>

<div class="part">
	<header class="head">
		<p class="label"><a href="{base}/parts">Parts</a> · {PART_CATEGORY_NAMES[data.part.category] ?? data.part.category}</p>
		<h1 class="mono">{data.part.value}</h1>
		<p class="lede">{data.rows.length} {data.rows.length === 1 ? 'circuit uses' : 'circuits use'} this part{#if data.part.types.length}. Listed as: {data.part.types.join('; ')}{/if}.</p>
	</header>
	<CircuitTable rows={data.rows} />
</div>

<style>
	.part { padding: 24px var(--gutter) 48px; max-width: 1180px; }
	.head { margin-bottom: 16px; }
	.head h1 { font-size: clamp(30px, 4.5vw, 44px); margin: 4px 0 8px; font-family: var(--mono); font-weight: 600; letter-spacing: 0; }
	.lede { color: var(--ink-2); max-width: 70ch; }
</style>
