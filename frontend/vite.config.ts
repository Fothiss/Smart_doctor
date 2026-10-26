import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

/**
 * Адрес бэкенда для dev-прокси.
 *
 * Прод отдаётся nginx'ом (`frontend/nginx.conf`), который сам проксирует `/api/` на сервис
 * `backend`. Локально тот же путь закрывает Vite, поэтому фронт всегда обращается к `/api`
 * относительным адресом и CORS не нужен. При смене `BACKEND_PORT`/`PORT` поправь значение здесь.
 */
const BACKEND_ORIGIN = 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      '/api': { target: BACKEND_ORIGIN },
    },
  },
  preview: {
    port: 4173,
    proxy: {
      '/api': { target: BACKEND_ORIGIN },
    },
  },
  test: {
    // Логика и вёрстка тестируются без браузера; jsdom подключается в отдельных тестах оверлеев
    environment: 'node',
    setupFiles: ['./src/test/setup.ts'],
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
