import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    // Bind to all interfaces so the dev server is reachable on your LAN/DNS
    host: true,
    port: parseInt(process.env.VITE_FRONTEND_PORT || '3000'),
    // If accessing via a hostname and you see HMR issues, set VITE_HOST env var
    // and uncomment the hmr.host below, or pass --host on the CLI.
    // Allow access from the hostname (configurable via environment)
    allowedHosts: [
      process.env.VITE_HOSTNAME || 'whyland-ai.nakedsun.xyz',
      'localhost', 
      '127.0.0.1'
    ],
    // Enable HMR for hostname access
    hmr: { 
      host: process.env.VITE_HOSTNAME || 'whyland-ai.nakedsun.xyz',
      port: parseInt(process.env.VITE_FRONTEND_PORT || '3000')
    },
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true,
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/ws/, '/api/v1/ws'),
      },
    },
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],
          ui: ['@headlessui/react', '@heroicons/react'],
          state: ['zustand'],
        },
      },
    },
  },
})