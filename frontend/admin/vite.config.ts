import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@shared': path.resolve(__dirname, '../shared'),
    },
  },
  server: {
    // monorepo: allow importing sibling workspace files (e.g. ../mini-program/app.json)
    fs: {
      allow: [path.resolve(__dirname, '..')],
    },
    proxy: {
      // 后端默认 uvicorn 8000；本地开发让 /api/* 走后端
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      // 图片/静态资源：/static/uploads/... 由后端 StaticFiles 提供
      '/static': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
})
