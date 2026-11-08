import { loadMeta } from '#lib/data.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ meta: await loadMeta(fetch) });
