import { base } from '$app/paths';
import type { Circuit, IndexEntry, PartEntry, VendorInfo } from './types';

let indexPromise: Promise<IndexEntry[]> | null = null;
let partsPromise: Promise<PartEntry[]> | null = null;
let vendorsPromise: Promise<Record<string, VendorInfo>> | null = null;
const circuitCache = new Map<string, Promise<Circuit>>();

type Fetch = typeof fetch;

async function getJson<T>(fetchFn: Fetch, path: string): Promise<T> {
	const res = await fetchFn(`${base}/data/${path}`);
	if (!res.ok) throw new Error(`${path}: ${res.status}`);
	return (await res.json()) as T;
}

export function loadIndex(fetchFn: Fetch = fetch): Promise<IndexEntry[]> {
	indexPromise ??= getJson<IndexEntry[]>(fetchFn, 'index.json');
	return indexPromise;
}

export function loadParts(fetchFn: Fetch = fetch): Promise<PartEntry[]> {
	partsPromise ??= getJson<PartEntry[]>(fetchFn, 'parts.json');
	return partsPromise;
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
	}
	return p;
}
