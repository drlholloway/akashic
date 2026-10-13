import { loadIndex, loadNeeds, loadParts } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => {
	const [index, parts, needs] = await Promise.all([loadIndex(fetch), loadParts(fetch), loadNeeds(fetch)]);
	return { index, parts, needs };
};
