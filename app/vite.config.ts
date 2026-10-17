import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'Akashic: Guitar Effects Circuit Lookup',
				short_name: 'Akashic',
				description: 'Guitar effects circuit lookup: every DIY pedal circuit, its parts list, and where to buy the board or find the layout.',
				theme_color: '#1c1f22',
				background_color: '#f4f2ee',
				display: 'standalone',
				start_url: '/',
				icons: [
					{ src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
					{ src: 'icon-512.png', sizes: '512x512', type: 'image/png' },
					{ src: 'icon-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' }
				]
			},
			workbox: {
				// Precached for every visitor: the app, the five top pages and the library's indexes. The 8,700
				// circuit pages, the part pages and the bundles of circuit records are cached as they are opened
				// (precaching them all cost a new visitor some 28,000 requests and 800 MB).
				globPatterns: ['**/*.{js,css,html,svg,png,woff2,json}'],
				globIgnores: ['**/circuit/**', '**/parts/**', '**/data/circuits/**', '**/data/sets/**', '**/data/owner/**'],
				maximumFileSizeToCacheInBytes: 16 * 1024 * 1024, // data/index.json is 7 MB
				// A page that is not precached comes from the network, never the home page in its place.
				navigateFallbackDenylist: [/^\/circuit\//, /^\/parts\//, /^\/data\//, /^\/datasheets\//, /^\/kicad\//],
				// Pages read their query in the browser (?share=, ?bench=1), so a precached page answers with any query:
				// otherwise /workbench/bench?share=… misses the cache and gets the home page as the fallback.
				ignoreURLParametersMatching: [/.*/],
				runtimeCaching: [
					{
						urlPattern: ({ url }) => url.pathname.startsWith('/data/sets/') || url.pathname.startsWith('/data/owner/'),
						handler: 'StaleWhileRevalidate',
						options: { cacheName: 'circuits', expiration: { maxEntries: 2000 } }
					},
					{
						urlPattern: ({ url, request }) => request.mode === 'navigate' && (url.pathname.startsWith('/circuit/') || url.pathname.startsWith('/parts/')),
						handler: 'StaleWhileRevalidate',
						options: { cacheName: 'pages', expiration: { maxEntries: 1000 } }
					}
				]
			}
		})
	]
});
