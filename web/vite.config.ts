import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    tsconfigPaths: true,
  },
  // O .env do projeto fica na raiz do repositório, não em web/ (CLAUDE.md da raiz).
  // Sem isso, o Vite só olha web/.env* e VITE_API_URL do .env da raiz é ignorada.
  envDir: '..',
  server: {
    proxy: { '/api': { target: 'http://localhost:8000', rewrite: (p) => p.replace(/^\/api/, '') } },
  },
  test: { environment: 'jsdom' },
})
