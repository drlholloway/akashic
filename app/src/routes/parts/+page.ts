import { loadParts } from '#lib/data.ts';
import type { PageLoad } from './$types';

export const load: PageLoad = async ({ fetch }) => ({ parts: await loadParts(fetch) });
