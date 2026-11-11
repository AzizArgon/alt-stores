import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { BRAND } from './src/config/brand.js'

// The browser tab title comes from the same config as the rest of the interface
const brandTitle = { name: 'brand-title', transformIndexHtml: (html) => html.replace('%BRAND_NAME%', BRAND.name) }

export default defineConfig({
  plugins: [react(), tailwindcss(), brandTitle],
  server: { port: 5173 },
  // Tests render components without the dev plugin's transform: the same automatic JSX runtime as the app
  esbuild: { jsx: 'automatic' },
})
