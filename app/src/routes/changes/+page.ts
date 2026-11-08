import { loadChanges } from '#lib/data.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ weeks: await loadChanges(fetch) });
