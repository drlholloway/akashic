import { loadIndex, loadParts } from '#lib/data.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [index, parts] = await Promise.all([loadIndex(fetch), loadParts(fetch)]);
	return { index, parts };
};
