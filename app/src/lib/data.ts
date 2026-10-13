import { browser } from '$app/environment';
import { base } from '$app/paths';
import type { ChangeWeek, Circuit, IndexEntry, Needs, PartEntry, SubsEntry, VendorInfo } from './types';

let indexPromise: Promise<IndexEntry[]> | null = null;
let partsPromise: Promise<PartEntry[]> | null = null;
let vendorsPromise: Promise<Record<string, VendorInfo>> | null = null;
let subsPromise: Promise<Record<string, SubsEntry>> | null = null;
const circuitCache = new Map<string, Promise<Circuit>>();

type Fetch = typeof fetch;

async function getJson<T>(fetchFn: Fetch, path: string): Promise<T> {
	const res = await fetchFn(`${base}/data/${path}`);
	if (!res.ok) throw new Error(`${path}: ${res.status}`);
	return (await res.json()) as T;
}

/** The library-wide files (7 MB and 3 MB). While prerendering they are read from disk, not fetched: SvelteKit
 *  writes every response a page's load fetches into that page's HTML, which made the circuits page 8 MB.
 *  In the browser they are fetched once and shared by every page. */
async function getLibraryJson<T>(fetchFn: Fetch, path: string): Promise<T> {
	if (browser) return getJson<T>(fetchFn, path);
	const { readFileSync } = await import('node:fs');
	return JSON.parse(readFileSync(`static/data/${path}`, 'utf8')) as T;
}

export function loadIndex(fetchFn: Fetch = fetch): Promise<IndexEntry[]> {
	indexPromise ??= getLibraryJson<IndexEntry[]>(fetchFn, 'index.json');
	return indexPromise;
}

export function loadParts(fetchFn: Fetch = fetch): Promise<PartEntry[]> {
	partsPromise ??= getLibraryJson<PartEntry[]>(fetchFn, 'parts.json');
	return partsPromise;
}

let needsPromise: Promise<Needs> | null = null;
export function loadNeeds(fetchFn: Fetch = fetch): Promise<Needs> {
	needsPromise ??= getLibraryJson<Needs>(fetchFn, 'needs.json');
	return needsPromise;
}

export interface LibraryMeta {
	generated_at: string;
	circuits: number;
	sources: number;
	parts_rows: number;
	part_values: number;
	delisted: number;
}

export function loadMeta(fetchFn: Fetch = fetch): Promise<LibraryMeta> {
	return getJson<LibraryMeta>(fetchFn, 'meta.json');
}

export function loadChanges(fetchFn: Fetch = fetch): Promise<ChangeWeek[]> {
	return getJson<ChangeWeek[]>(fetchFn, 'changes.json');
}

export function loadVendors(fetchFn: Fetch = fetch): Promise<Record<string, VendorInfo>> {
	vendorsPromise ??= getJson<Record<string, VendorInfo>>(fetchFn, 'vendors.json');
	return vendorsPromise;
}

export function loadCircuit(fileId: string, fetchFn: Fetch = fetch): Promise<Circuit> {
	let p = circuitCache.get(fileId);
	if (!p) {
		p = getJson<Circuit>(fetchFn, `circuits/${fileId}.json`);
		circuitCache.set(fileId, p);
		p.catch(() => circuitCache.delete(fileId)); // a failed fetch (offline) is tried again on the next visit
	}
	return p;
}

export function loadSubs(fetchFn: Fetch = fetch): Promise<Record<string, SubsEntry>> {
	subsPromise ??= getJson<Record<string, SubsEntry>>(fetchFn, 'subs.json').catch(() => ({}));
	return subsPromise;
}
