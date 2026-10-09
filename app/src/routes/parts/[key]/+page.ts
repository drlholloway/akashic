import { error } from '@sveltejs/kit';
import { loadIndex, loadParts, loadSubs } from '$lib/data';
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
	const subs = part.category === 'Q' ? (await loadSubs(fetch))[part.value.toUpperCase()] ?? null : null;
	const bySlug = new Map(parts.map((p) => [p.value.toUpperCase(), p.slug]));
	// a zener's other grades and spellings are the same part here: 1N4739, 1N4739A; BZX79C9V1, BZX79-C9V1
	const same = (pn: string) => {
		const base = pn.replace(/^(1N\d+)[AB]$/, '$1');
		const rx = base.startsWith('1N') ? new RegExp(`^${base}[A-D]?$`) : new RegExp(`^${base.replace(/^(BZX\d\d)C/, '$1-?C')}$`);
		return parts.filter((p) => p.category === 'D' && rx.test(p.value.toUpperCase()));
	};
	const zeners = Object.fromEntries((part.zeners ?? []).map((z) => {
		const found = same(z.pn).sort((a, b) => b.count - a.count);
		return [z.pn, { boards: new Set(found.flatMap((p) => p.circuits)).size, slug: found.find((p) => p.value.toUpperCase() === z.pn)?.slug ?? found[0]?.slug ?? '' }];
	}));
	return { part, rows: index.filter((e) => ids.has(e.id)), subs, partSlugs: Object.fromEntries(bySlug), zeners };
};
