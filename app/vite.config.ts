import { sveltekit } from '@sveltejs/kit/vite';
import { SvelteKitPWA } from '@vite-pwa/sveltekit';
import { defineConfig } from 'vite';

export default defineConfig({
	plugins: [
		sveltekit(),
		SvelteKitPWA({
			registerType: 'autoUpdate',
			manifest: {
				name: 'Akashic: Guitar Effects PCB Lookup',
				short_name: 'Akashic',
				description: 'Guitar effects PCB lookup: every DIY pedal circuit, its parts list, and where to buy the board.',
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
				globPatterns: ['**/*.{js,css,html,svg,png,woff2,json}'],
				maximumFileSizeToCacheInBytes: 8 * 1024 * 1024,
				runtimeCaching: [
					{
						urlPattern: ({ url }) => url.pathname.startsWith('/data/circuits/'),
						handler: 'StaleWhileRevalidate',
						options: { cacheName: 'circuits', expiration: { maxEntries: 2000 } }
					}
				]
			}
		})
	]
});
