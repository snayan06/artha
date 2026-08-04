import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { defineConfig } from 'vite'

export default defineConfig({
  // Keep one root-level environment file for both the web app and API.
  envDir: '../..',
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          charts: ['recharts']
        }
      }
    }
  },
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg'],
      manifest: {
        name: 'Artha',
        short_name: 'Artha',
        description: 'Track money in five seconds, understand it anytime.',
        theme_color: '#173f35',
        background_color: '#f5f7f2',
        display: 'standalone',
        start_url: '/',
        orientation: 'portrait-primary',
        icons: [
          { src: '/pwa-192x192.svg', sizes: '192x192', type: 'image/svg+xml', purpose: 'any' },
          { src: '/pwa-512x512.svg', sizes: '512x512', type: 'image/svg+xml', purpose: 'any maskable' }
        ]
      },
      workbox: {
        navigateFallbackDenylist: [/^\/api/],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkOnly'
          }
        ]
      }
    })
  ]
})
