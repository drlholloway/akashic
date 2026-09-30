import { loadMeta } from '$lib/data';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ meta: await loadMeta(fetch) });
