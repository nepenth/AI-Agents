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
    host: '0.0.0.0',
    port: parseInt(process.env.VITE_FRONTEND_PORT || '3000'),
    // Allow access from the hostname (configurable via environment)
    allowedHosts: [
      process.env.VITE_HOSTNAME || 'whyland-ai',
      'localhost', 
      '127.0.0.1'
    ],
    // Enable HMR for hostname access
    hmr: { 
      host: process.env.VITE_HOSTNAME || 'whyland-ai',
      port: parseInt(process.env.VITE_FRONTEND_PORT || '3000')
    },
    proxy: {
      '/api': {
        target: `http://${process.env.VITE_HOSTNAME || 'whyland-ai'}:${process.env.VITE_BACKEND_PORT || '8000'}`,
        changeOrigin: true,
        secure: false,
      },
      '/ws': {
        target: `ws://${process.env.VITE_HOSTNAME || 'whyland-ai'}:${process.env.VITE_BACKEND_PORT || '8000'}`,
        ws: true,
        changeOrigin: true,
        secure: false,
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