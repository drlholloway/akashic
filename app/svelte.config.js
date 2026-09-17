import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
	preprocess: vitePreprocess(),
	kit: {
		adapter: adapter({ fallback: '404.html' }),
		// Circuit and part pages come from the exported data; an empty export (as in CI)
		// legitimately produces none, so unseen dynamic routes are not an error.
		prerender: { handleHttpError: 'warn', handleMissingId: 'ignore', handleUnseenRoutes: 'ignore' }
	}
};

export default config;
