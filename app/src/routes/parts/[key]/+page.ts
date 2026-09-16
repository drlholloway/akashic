import { error } from '@sveltejs/kit';
import { loadIndex, loadParts } from '$lib/data';
import type { EntryGenerator, PageLoad } from './$types';

export const entries: EntryGenerator = async () => {
	const { readFileSync } = await import('node:fs');
	const parts = JSON.parse(readFileSync('static/data/parts.json', 'utf8')) as { slug: string }[];
	return parts.map((p) => ({ key: p.slug }));
};

export const load: PageLoad = async ({ params, fetch }) => {
	const [parts, index] = await Promise.all([loadParts(fetch), loadIndex(fetch)]);
	const part = parts.find((p) => p.slug === params.key);
	if (!part) error(404, 'No such part');
	const ids = new Set(part.circuits);
	return { part, rows: index.filter((e) => ids.has(e.id)) };
};
