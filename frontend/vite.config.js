import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'
import { COLORS } from './src/lib/palette.js'

/**
 * `index.html` è un file statico: da solo non può leggere `palette.js`. Questo innesto
 * sostituisce i segnaposto col colore vero al momento della compilazione, così anche la
 * barra del browser segue la palette invece di una copia scritta a mano — che è
 * esattamente il pezzo che si dimentica quando si cambia il colore d'accento.
 */
function palettePlaceholders() {
  return {
    name: 'palette-placeholders',
    transformIndexHtml(html) {
      return html
        .replaceAll('__COLOR_ACCENT__', COLORS.accent)
        .replaceAll('__COLOR_BACKGROUND__', COLORS.background)
    },
  }
}

export default defineConfig({
  plugins: [
    react(),
    palettePlaceholders(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'Wrap',
        short_name: 'Wrap',
        theme_color: COLORS.accent,
        background_color: COLORS.background,
        display: 'standalone',
        start_url: '/',
        icons: [
          {
            src: '/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        globPatterns: ['**/*.{js,css,html,ico,png,svg,woff2}'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/(auth|api|health)/],
        runtimeCaching: [
          {
            urlPattern: /^https:\/\/fonts\.googleapis\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'google-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /^https:\/\/fonts\.gstatic\.com\/.*/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'gstatic-fonts-cache',
              expiration: {
                maxEntries: 10,
                maxAgeSeconds: 60 * 60 * 24 * 365, // 1 year
              },
              cacheableResponse: {
                statuses: [0, 200],
              },
            },
          },
          {
            urlPattern: /\.(?:js|css|woff2?|png|jpg|jpeg|svg|gif|ico)$/i,
            handler: 'CacheFirst',
            options: {
              cacheName: 'static-assets-cache',
              expiration: {
                maxEntries: 100,
                maxAgeSeconds: 60 * 60 * 24 * 30, // 30 days
              },
            },
          },
          {
            urlPattern: /^\/(api|auth)\/.*/i,
            handler: 'NetworkOnly',
          },
        ],
      },
      // Do NOT enable devOptions — it interferes with Vite proxy
    }),
  ],
  server: {
    host: '127.0.0.1',
    port: 5173,
    proxy: {
      '/auth': 'http://127.0.0.1:8001',
      '/api': 'http://127.0.0.1:8001',
      '/health': 'http://127.0.0.1:8001',
    },
  },
})
