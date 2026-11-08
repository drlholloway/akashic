import { loadIndex } from '#lib/data.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	return { index: await loadIndex(fetch) };
};
