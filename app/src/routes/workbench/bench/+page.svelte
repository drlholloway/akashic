<script lang="ts">
	import { browser } from '$app/environment';
	import { base } from '$app/paths';
	import { page } from '$app/state';
	import { bench } from '$lib/bench.svelte';
	import { currency } from '$lib/currency.svelte';
	import { VENDOR_NAMES, type IndexEntry } from '$lib/types';

	let { data } = $props();
	const byId = $derived(new Map(data.index.map((e) => [e.id, e])));
	const byFile = $derived(new Map(data.index.map((e) => [e.file_id, e])));
	const rows = $derived(bench.ids.map((id) => byId.get(id)).filter((e): e is IndexEntry => !!e));

	// A share link carries the circuits (not the notes) in the address: ?share=file_id,file_id
	let shared = $state<IndexEntry[]>([]);
	$effect(() => {
		if (!browser) return;
		const s = page.url.searchParams.get('share') ?? '';
		shared = s.split(',').map((f) => byFile.get(f.trim())).filter((e): e is IndexEntry => !!e);
	});
	const sharedNew = $derived(shared.filter((e) => !bench.has(e.id)));

	let status = $state('');
	const say = (msg: string) => {
		status = msg;
		setTimeout(() => status === msg && (status = ''), 4000);
	};
	async function copyLink() {
		const url = `${location.origin}${base}/workbench/bench?share=${rows.map((e) => e.file_id).join(',')}`;
		try {
			await navigator.clipboard.writeText(url);
			say(`Link to ${rows.length} ${rows.length === 1 ? 'circuit' : 'circuits'} copied. Notes stay here.`);
		} catch {
			say('The browser would not copy the link.');
		}
	}
	function exportFile() {
		const a = document.createElement('a');
		a.href = URL.createObjectURL(new Blob([bench.exportFile()], { type: 'application/json' }));
		a.download = `akashic-bench-${new Date().toISOString().slice(0, 10)}.json`;
		a.click();
		setTimeout(() => URL.revokeObjectURL(a.href), 1000);
	}
	let picker: HTMLInputElement | undefined = $state();
	async function importFile(ev: Event) {
		const file = (ev.currentTarget as HTMLInputElement).files?.[0];
		if (!file) return;
		try {
			const r = bench.importFile(await file.text(), (id) => byId.has(id));
			say(`Added ${r.circuits} ${r.circuits === 1 ? 'circuit' : 'circuits'}${r.parts ? ` and ${r.parts} ${r.parts === 1 ? 'part' : 'parts'} to What can I build` : ''}.`);
		} catch {
			say('That file is not an Akashic bench export.');
		}
		if (picker) picker.value = '';
	}
	// Clearing takes a second click, so a slip does not empty the bench.
	let clearing = $state(false);
	function clear() {
		if (!clearing) {
			clearing = true;
			setTimeout(() => (clearing = false), 4000);
			return;
		}
		bench.clear();
		clearing = false;
	}
</script>

<svelte:head><title>My bench · Akashic</title></svelte:head>

<h1>My bench</h1>
<p class="lede">The circuits you keep, with a note on each. Add one with the <span class="mono">+ My bench</span> button on its page. The bench is kept in this browser only: export it to move it to another device or keep a copy, since clearing site data erases it, and Safari does after seven days without a visit unless Akashic is installed to the home screen.</p>

{#if sharedNew.length}
	<div class="shared">
		<p class="label strong">A shared bench · {shared.length} {shared.length === 1 ? 'circuit' : 'circuits'}{#if sharedNew.length < shared.length}, {sharedNew.length} not on yours{/if}</p>
		<ul>
			{#each sharedNew as e (e.id)}
				<li><a href="{base}/circuit/{e.file_id}">{e.name}</a> <span class="dim">{VENDOR_NAMES[e.vendor]}</span></li>
			{/each}
		</ul>
		<button type="button" class="btn" onclick={() => sharedNew.forEach((e) => bench.add(e.id))}>Add {sharedNew.length === 1 ? 'it' : `all ${sharedNew.length}`} to my bench</button>
	</div>
{/if}

<div class="tools">
	<span class="label strong count">{rows.length} {rows.length === 1 ? 'circuit' : 'circuits'}</span>
	{#if rows.length}
		<a class="btn ghost" href="{base}/?bench=1">Open in Circuits</a>
		<a class="btn ghost" href="{base}/workbench/build?bench=1">What can I build from it</a>
		<button type="button" class="btn ghost" onclick={copyLink}>Copy share link</button>
		<button type="button" class="btn ghost" onclick={exportFile}>Export</button>
	{/if}
	<button type="button" class="btn ghost" onclick={() => picker?.click()}>Import</button>
	<input bind:this={picker} type="file" accept="application/json,.json" class="sr-only" onchange={importFile} tabindex="-1" aria-hidden="true" />
	{#if rows.length}<button type="button" class="label clear" class:arm={clearing} onclick={clear}>{clearing ? 'Click again to clear the bench' : 'Clear the bench'}</button>{/if}
</div>
<p class="status" aria-live="polite">{status}</p>

{#if rows.length}
	<table class="sheet-table">
		<thead><tr><th>Circuit</th><th class="src">Source</th><th class="cat">Type</th><th class="n">Price</th><th>Note</th><th class="added">Added</th><th><span class="sr-only">Remove</span></th></tr></thead>
		<tbody>
			{#each rows as e (e.id)}
				<tr>
					<td>
						<a class="name" href="{base}/circuit/{e.file_id}">{e.name}</a>
						{#if e.original && e.original !== e.name}<span class="dim orig">{e.original}</span>{/if}
						{#if e.delisted}<span class="warn orig">No longer listed</span>{/if}
					</td>
					<td class="src dim">{VENDOR_NAMES[e.vendor]}</td>
					<td class="cat dim">{e.category}</td>
					<td class="n mono">{currency.format(e.price, e.currency) || '—'}</td>
					<td class="note"><input type="text" value={bench.items[e.id]?.note ?? ''} oninput={(ev) => bench.setNote(e.id, ev.currentTarget.value)} placeholder="Add a note" maxlength="300" aria-label="Note on {e.name}" /></td>
					<td class="added mono dim">{bench.items[e.id]?.added}</td>
					<td><button type="button" class="x" onclick={() => bench.remove(e.id)} aria-label="Take {e.name} off the bench" title="Take it off the bench">×</button></td>
				</tr>
			{/each}
		</tbody>
	</table>
{:else}
	<div class="empty">
		<p class="label strong">Nothing on the bench yet</p>
		<p>Find a circuit you like in <a href="{base}/">Circuits</a> and press <span class="mono">+ My bench</span> on its page. It shows up here, marked in the circuits table, and as a filter there and in What can I build.</p>
	</div>
{/if}

<style>
	.dim { color: var(--ink-3); }
	.shared { border: 1px solid var(--coat); background: var(--coat-tint); border-radius: var(--radius); padding: 14px 18px; margin-bottom: 18px; max-width: 78ch; }
	.shared ul { list-style: none; margin: 8px 0 12px; padding: 0; display: grid; gap: 2px; }
	.shared a, .empty a { text-decoration: underline; text-decoration-color: var(--rule-strong); text-underline-offset: 3px; }
	.tools { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; }
	.tools .count { margin-right: 8px; }
	.tools .btn { padding: 6px 12px; font-size: 13px; }
	.clear { background: none; border: 0; padding: 4px 6px; cursor: pointer; text-decoration: underline; text-underline-offset: 3px; }
	.clear:hover, .clear.arm { color: var(--warn); }
	.status { min-height: 1.4em; margin: 6px 0 4px; color: var(--ink-2); font-size: 14px; }
	.name { font-weight: 600; }
	.orig { display: block; font-size: 13px; }
	.note { width: 34%; }
	.note input { width: 100%; height: 30px; padding: 0 8px; border: 1px solid transparent; border-radius: var(--radius); background: transparent; color: var(--ink); font: inherit; font-size: 14px; }
	.note input:hover { border-color: var(--rule); }
	.note input:focus { outline: none; border-color: var(--coat); background: var(--sheet); }
	.x { height: 28px; border: 0; background: none; color: var(--ink-3); font-size: 18px; line-height: 1; cursor: pointer; border-radius: var(--radius); }
	.x:hover { color: var(--warn); background: var(--sheet-2); }
	.empty { border: 1px dashed var(--rule-strong); border-radius: var(--radius); padding: 20px 22px; max-width: 62ch; margin-top: 8px; }
	.empty p { margin: 0 0 6px; color: var(--ink-2); }
	@media (max-width: 860px) { .src, .added { display: none; } }
	@media (max-width: 560px) { .cat { display: none; } .note { width: auto; } }
</style>
