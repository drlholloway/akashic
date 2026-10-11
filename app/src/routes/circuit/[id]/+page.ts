import { browser } from '$app/environment';
import { error } from '@sveltejs/kit';
import { loadCircuit, loadIndex } from '$lib/data';
import type { EntryGenerator, PageLoad } from './$types';

export const entries: EntryGenerator = async () => {
	const { readFileSync } = await import('node:fs');
	const index = JSON.parse(readFileSync('static/data/index.json', 'utf8')) as { file_id: string }[];
	return index.map((e) => ({ id: e.file_id }));
};

export const load: PageLoad = async ({ params, fetch }) => {
	const [circuit, index] = await Promise.all([loadCircuit(params.id, fetch).catch(() => null), loadIndex(fetch)]);
	// Offline, a circuit opens only if it was opened on this device before; say that, not 'no such circuit'.
	if (!circuit && browser && (!navigator.onLine || index.some((e) => e.file_id === params.id)))
		error(503, 'This circuit could not be loaded. If you are offline, only circuits you have already opened on this device are available.');
	if (!circuit) error(404, 'No such circuit');
	return { circuit, index };
};
