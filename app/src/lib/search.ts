import MiniSearch from 'minisearch';
import type { IndexEntry } from './types';
import { VENDOR_NAMES } from './types';
import { controlLabels, controlSearchText } from './controls';

export interface Filters {
	q: string;
	vendor: string[];
	category: string[];
	enclosure: string[];
	basedOn: string; // exact match on based_on
	part: string; // active part value (IC/Q/OPTO) exact match
	knobs: number | null;
	control: string[]; // control groups ('Blend', 'Bias'); a circuit must have every one
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
	control: [],
	inStock: false
};

let mini: MiniSearch<IndexEntry> | null = null;
// Control names ('Blend', 'PRES', and each control's synonyms) in an index of their own, matched on
// whole words only: with prefix matching, 'rat' would find every circuit with a Rate knob.
let controlsMini: MiniSearch<IndexEntry> | null = null;
const SPACE_OR_PUNCTUATION = /[\n\r\p{Z}\p{P}]+/u; // MiniSearch's own tokenizer
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
				case 'activesText':
					return doc.actives.join(' ');
				default:
					return (doc as unknown as Record<string, string>)[field];
			}
		}
	});
	mini.addAll(entries);
	controlsMini = new MiniSearch<IndexEntry>({
		fields: ['controlsText'],
		storeFields: ['id'],
		searchOptions: { prefix: false, fuzzy: false },
		extractField: (doc, field) => (field === 'controlsText' ? controlSearchText(doc.controls) : (doc as unknown as Record<string, string>)[field])
	});
	controlsMini.addAll(entries);
	indexed = entries;
}

export function applyFilters(entries: IndexEntry[], f: Filters): IndexEntry[] {
	let ids: Set<string> | null = null;
	let rank: Map<string, number> | null = null;
	const q = f.q.trim();
	if (q && mini && controlsMini) {
		// Every word must match (AND), in the main fields or as a control name; scores add up.
		let score: Map<string, number> | null = null;
		for (const t of q.split(SPACE_OR_PUNCTUATION).filter(Boolean)) {
			const m = new Map<string, number>();
			for (const r of mini.search(t)) m.set(r.id as string, r.score);
			for (const r of controlsMini.search(t)) m.set(r.id as string, (m.get(r.id as string) ?? 0) + r.score * 0.5);
			score = score ? new Map([...m].filter(([id]) => score!.has(id)).map(([id, s]) => [id, s + score!.get(id)!])) : m;
		}
		const ranked = [...(score ?? new Map<string, number>())].sort((a, b) => b[1] - a[1]);
		rank = new Map(ranked.map(([id], i) => [id, i]));
		ids = new Set(rank.keys());
	}
	const knobsOf = (e: IndexEntry) => {
		const m = e.controls.length === 1 && /^(\d+) knobs?$/.exec(e.controls[0]);
		return m ? Number(m[1]) : e.controls.length;
	};
	// A link may carry a vendor's own spelling ('EHX Big Muff', from before originals were settled):
	// resolve it to the original that spelling now belongs to, so it opens the whole group.
	let basedKey = f.basedOn ? normalizeOriginal(f.basedOn) : '';
	if (basedKey && !entries.some((e) => normalizeOriginal(e.original) === basedKey)) {
		const hit = entries.find((e) => e.original && normalizeOriginal(e.based_on) === basedKey);
		if (hit) basedKey = normalizeOriginal(hit.original);
	}
	const out = entries.filter((e) => {
		if (ids && !ids.has(e.id)) return false;
		if (f.vendor.length && !f.vendor.includes(e.vendor)) return false;
		if (f.category.length && !f.category.includes(e.category)) return false;
		if (f.enclosure.length && !f.enclosure.includes(e.enclosure)) return false;
		if (basedKey && normalizeOriginal(e.original) !== basedKey && normalizeOriginal(e.based_on) !== basedKey) return false;
		if (f.part && !e.actives.includes(f.part)) return false;
		if (f.knobs != null && knobsOf(e) !== f.knobs) return false;
		if (f.control.length) {
			const has = controlLabels(e.controls);
			if (!f.control.every((c) => has.has(c))) return false;
		}
		if (f.inStock && (e.in_stock !== true || e.delisted)) return false;
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
		control: list('ctl'),
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
	if (f.control.length) p.set('ctl', f.control.join(','));
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
