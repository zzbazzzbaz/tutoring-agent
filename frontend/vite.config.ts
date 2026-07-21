import { defineConfig } from 'vite'
import path from 'path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: 8001,
    strictPort: true,
    allowedHosts: ['8001.frp.chatgqt.top'],
    hmr: {
      protocol: 'wss',
      host: '8001.frp.chatgqt.top',
      port: 443,
      clientPort: 443,
    },
    proxy: {
      '/health': 'http://localhost:8000',
      '/auth': 'http://localhost:8000',
      '/users': 'http://localhost:8000',
      '/projects': 'http://localhost:8000',
      '/sessions': 'http://localhost:8000',
      '/chat': 'http://localhost:8000',
    },
  },
})
