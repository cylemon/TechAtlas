import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// 后端地址，需要时用 VITE_BACKEND_URL 覆盖
const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      // 开发时把 /api 转发给后端：前端视角下是同源请求，
      // 因此完全不涉及 CORS，也不必去配后端的 CORS_ALLOW_ORIGINS
      '/api': { target: backend, changeOrigin: true },
    },
  },
})
