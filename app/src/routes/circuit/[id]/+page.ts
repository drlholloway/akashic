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
	if (!circuit) error(404, 'No such circuit');
	return { circuit, index };
};
