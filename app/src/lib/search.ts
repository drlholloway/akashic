import MiniSearch from 'minisearch';
import type { IndexEntry } from './types';
import { VENDOR_NAMES } from './types';

export interface Filters {
	q: string;
	vendor: string[];
	category: string[];
	enclosure: string[];
	basedOn: string; // exact match on based_on
	part: string; // active part value (IC/Q/OPTO) exact match
	knobs: number | null;
	inStock: boolean;
}

export const EMPTY_FILTERS: Filters = {
	q: '',
	vendor: [],
	category: [],
	enclosure: [],
	basedOn: '',
	part: '',
	knobs: null,
	inStock: false
};

let mini: MiniSearch<IndexEntry> | null = null;
let indexed: IndexEntry[] = [];

export function buildSearch(entries: IndexEntry[]): void {
	if (mini && indexed === entries) return;
	mini = new MiniSearch<IndexEntry>({
		fields: ['name', 'subtitle', 'based_on', 'category', 'effect_type', 'vendorName', 'enclosure', 'tagsText', 'activesText'],
		storeFields: ['id'],
		searchOptions: {
			boost: { name: 4, based_on: 3, activesText: 2 },
			prefix: true,
			fuzzy: (term) => (term.length > 4 ? 0.2 : false),
			combineWith: 'AND'
		},
		extractField: (doc, field) => {
			switch (field) {
				case 'vendorName':
					return VENDOR_NAMES[doc.vendor];
				case 'tagsText':
					return doc.tags.join(' ');
				case 'controlsText':
					return doc.controls.join(' ');
				case 'activesText':
					return doc.actives.join(' ');
				default:
					return (doc as unknown as Record<string, string>)[field];
			}
		}
	});
	mini.addAll(entries);
	indexed = entries;
}

export function applyFilters(entries: IndexEntry[], f: Filters): IndexEntry[] {
	let ids: Set<string> | null = null;
	let rank: Map<string, number> | null = null;
	const q = f.q.trim();
	if (q && mini) {
		rank = new Map(mini.search(q).map((r, i) => [r.id as string, i]));
		ids = new Set(rank.keys());
	}
	const knobsOf = (e: IndexEntry) => {
		const m = e.controls.length === 1 && /^(\d+) knobs?$/.exec(e.controls[0]);
		return m ? Number(m[1]) : e.controls.length;
	};
	const out = entries.filter((e) => {
		if (ids && !ids.has(e.id)) return false;
		if (f.vendor.length && !f.vendor.includes(e.vendor)) return false;
		if (f.category.length && !f.category.includes(e.category)) return false;
		if (f.enclosure.length && !f.enclosure.includes(e.enclosure)) return false;
		if (f.basedOn && normalizeOriginal(e.based_on) !== normalizeOriginal(f.basedOn)) return false;
		if (f.part && !e.actives.includes(f.part)) return false;
		if (f.knobs != null && knobsOf(e) !== f.knobs) return false;
		if (f.inStock && e.in_stock !== true) return false;
		return true;
	});
	if (rank) out.sort((a, b) => rank!.get(a.id)! - rank!.get(b.id)!);
	return out;
}

export function filtersFromParams(p: URLSearchParams): Filters {
	const list = (k: string) => p.getAll(k).flatMap((v) => v.split(',')).filter(Boolean);
	const knobs = p.get('knobs');
	return {
		q: p.get('q') ?? '',
		vendor: list('vendor'),
		category: list('cat'),
		enclosure: list('enc'),
		basedOn: p.get('based') ?? '',
		part: p.get('part') ?? '',
		knobs: knobs ? Number(knobs) : null,
		inStock: p.get('stock') === '1'
	};
}

export function paramsFromFilters(f: Filters): URLSearchParams {
	const p = new URLSearchParams();
	if (f.q.trim()) p.set('q', f.q.trim());
	if (f.vendor.length) p.set('vendor', f.vendor.join(','));
	if (f.category.length) p.set('cat', f.category.join(','));
	if (f.enclosure.length) p.set('enc', f.enclosure.join(','));
	if (f.basedOn) p.set('based', f.basedOn);
	if (f.part) p.set('part', f.part);
	if (f.knobs != null) p.set('knobs', String(f.knobs));
	if (f.inStock) p.set('stock', '1');
	return p;
}

/** Group "based_on" values so the same original spelled slightly differently collapses. */
export function normalizeOriginal(s: string): string {
	return s
		.replace(/[®™]/g, '')
		.replace(/\b(the|a|an)\b/gi, '')
		.replace(/[^a-z0-9]+/gi, ' ')
		.trim()
		.toLowerCase();
}
