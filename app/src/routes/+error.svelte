<script lang="ts">
	import { page } from '$app/state';
	import { base } from '$app/paths';
</script>

<svelte:head><title>{page.status} · Akashic</title></svelte:head>

<div class="error">
	<h1>{page.status === 503 ? 'Not available' : page.status}</h1>
	<p>{page.error?.message}</p>
	<p><a href="{base}/">Back to the circuits</a></p>
</div>

<style>
	.error { padding: 24px var(--gutter) 48px; max-width: 70ch; }
	.error h1 { font-size: clamp(28px, 4vw, 40px); margin-bottom: 8px; }
	.error p { color: var(--ink-2); margin-bottom: 12px; }
</style>
