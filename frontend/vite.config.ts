import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [react(), tailwindcss(), VitePWA({
    strategies: 'injectManifest', srcDir: 'src', filename: 'sw.ts', registerType: 'prompt', injectRegister: null,
    includeAssets: ['brand/*', 'illustrations/*'],
    manifest: { name: 'SITRAP — Trazabilidad', short_name: 'SITRAP', description: 'Cada producto tiene una historia', lang: 'es-PE', start_url: '/', scope: '/', display: 'standalone', theme_color: '#237a57', background_color: '#f5f5f7', icons: [
      { src: '/brand/icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
      { src: '/brand/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' },
    ] },
    injectManifest: { globPatterns: ['**/*.{js,css,html,svg,png,webmanifest}'] },
  })],
  server: { proxy: { '/api/v1': 'http://127.0.0.1:8000' } },
  test: { globals: true, environment: 'jsdom', setupFiles: ['./src/test/setup.ts'], include: ['src/**/*.test.{ts,tsx}'] },
})
