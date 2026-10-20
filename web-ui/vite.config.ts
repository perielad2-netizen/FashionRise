/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

/**
 * Cloudflare Access sits in front of fashionrise.app.
 * Never precache HTML or install a Workbox NavigationRoute/navigateFallback:
 * a cached /index.html shell can satisfy /login|/register|/studio navigations
 * without an Access round-trip, so the following credentialed API calls fail
 * (Access 302 cross-origin → "Unable to reach FashionRise").
 * Nginx already serves SPA HTML via try_files; offline app shell is intentionally
 * not provided for document navigations.
 */
const pwaWorkbox = {
  // Versioned static assets only — no HTML shell.
  globPatterns: ['**/*.{js,css,ico,svg,woff2}', 'icons/*.png', 'branding/*.png'],
  globIgnores: ['**/models/**', '**/*.html', '**/index.html'],
  maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
  // vite-plugin-pwa defaults navigateFallback to 'index.html'. Explicit null
  // disables NavigationRoute generation (workbox-build accepts null).
  navigateFallback: null,
} as const

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: [
        'branding/fashion_rise_logo.png',
        'icons/favicon-32.png',
        'icons/apple-touch-icon.png',
      ],
      manifest: {
        name: 'FashionRise',
        short_name: 'FashionRise',
        description: 'Tablet-first fashion creation studio',
        theme_color: '#090F1F',
        background_color: '#090F1F',
        display: 'standalone',
        display_override: ['window-controls-overlay', 'standalone'],
        orientation: 'any',
        start_url: '/studio',
        scope: '/',
        icons: [
          {
            src: '/icons/icon-192.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      // Cast: plugin d.ts types navigateFallback as string only; workbox-build
      // accepts null to disable. Verified against generated dist/sw.js.
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      workbox: pwaWorkbox as any,
      devOptions: {
        enabled: false,
      },
    }),
  ],
  resolve: {
    alias: {
      '@': path.resolve(rootDir, './src'),
    },
  },
  server: {
    port: 5173,
    host: true,
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    globals: true,
  },
})
