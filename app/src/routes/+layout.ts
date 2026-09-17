import { base } from '$app/paths';
import type { Rates } from '$lib/currency.svelte';
import type { VendorInfo } from '$lib/types';
import type { LayoutLoad } from './$types';

export const prerender = true;
export const trailingSlash = 'never';

export const load: LayoutLoad = async ({ fetch }) => {
	let rates: Rates | null = null;
	try {
		const res = await fetch(`${base}/data/rates.json`);
		if (res.ok) rates = (await res.json()) as Rates;
	} catch {
		/* offline without a cached copy: prices show as listed */
	}
	let vendors: Record<string, VendorInfo> = {};
	try {
		const res = await fetch(`${base}/data/vendors.json`);
		if (res.ok) vendors = (await res.json()) as Record<string, VendorInfo>;
	} catch {
		/* footer just omits the vendor list */
	}
	return { rates, vendors };
};
