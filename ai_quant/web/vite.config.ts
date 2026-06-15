/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tsconfigPaths from 'vite-tsconfig-paths'

export default defineConfig({
  envDir: '..',
  server: {
    host: '0.0.0.0',
    port: Number(process.env.VITE_DEV_PORT) || 5173,
    proxy: {
      '/api': {
        target: process.env.VITE_API_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    sourcemap: 'hidden',
    modulePreload: false,
  },
  plugins: [
    react({
      babel: {
        plugins: process.env.NODE_ENV === 'development'
          ? ['react-dev-locator']
          : [],
      },
    }),
    tsconfigPaths(),
  ],
  test: {
    // 让 vitest 忽略 CSS import，加速测试启动
    css: false,
    // 不解析 node_modules 中的 Svelte / bytemd 相关文件
    server: {
      deps: {
        inline: [],
      },
    },
  },
})