/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

const rootDir = path.dirname(fileURLToPath(import.meta.url))

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
      workbox: {
        // Large croquis stay network-loaded; keep SW under size limits.
        globPatterns: ['**/*.{js,css,html,ico,svg,woff2}', 'icons/*.png', 'branding/*.png'],
        globIgnores: ['**/models/**'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
        // Do NOT cache navigations. fashionrise.app sits behind Cloudflare Access;
        // a NavigationRoute/navigateFallback for /index.html can serve /login from
        // the SW cache without an Access check. The following POST /api/v1/auth/login
        // then receives an Access 302 to another origin and fetch() fails with
        // "Unable to reach FashionRise". Nginx already try_files SPA fallbacks.
        navigateFallback: undefined,
      },
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
