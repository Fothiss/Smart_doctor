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
  plugins: [react()],
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
    // Тестируется только слой API и чистая логика: DOM и canvas в тестах не нужны
    environment: 'node',
    include: ['src/**/*.test.{ts,tsx}'],
  },
})
