import path from "path"
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // @ 别名指向 src，与 tsconfig paths 保持一致（shadcn/ui 组件依赖）
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // dev 下把 /api 与 /dev 转发到本地后端
      "/api": "http://127.0.0.1:8000",
      "/dev": "http://127.0.0.1:8000",
    },
  },
})
