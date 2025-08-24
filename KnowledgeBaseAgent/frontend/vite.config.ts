import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'
import { splitVendorChunkPlugin } from 'vite'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const isProduction = mode === 'production'
  const isDevelopment = mode === 'development'

  return {
    plugins: [
      react({
        // Enable React Fast Refresh in development
        fastRefresh: isDevelopment,
        // Optimize JSX in production
        jsxRuntime: 'automatic',
      }),
      // Split vendor chunks for better caching
      splitVendorChunkPlugin(),
    ],

    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },

    server: {
      // Bind to all interfaces so the dev server is reachable on your LAN/DNS
      host: true,
      port: parseInt(process.env.VITE_FRONTEND_PORT || '3000'),
      // Allow access from the hostname (configurable via environment)
      allowedHosts: [
        process.env.VITE_HOSTNAME || 'whyland-ai.nakedsun.xyz',
        'localhost',
        '127.0.0.1'
      ],
      // Enable HMR for hostname access
      hmr: {
        host: process.env.VITE_HOSTNAME || 'whyland-ai.nakedsun.xyz',
        port: parseInt(process.env.VITE_FRONTEND_PORT || '3000'),
        overlay: true,
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
      // Target modern browsers for smaller bundles
      target: 'es2020',

      // Source maps only in development
      sourcemap: isDevelopment,

      // Minification options
      minify: isProduction ? 'terser' : false,
      terserOptions: isProduction ? {
        compress: {
          // Remove console logs in production
          drop_console: true,
          drop_debugger: true,
          // Remove unused code
          dead_code: true,
          // Optimize conditionals
          conditionals: true,
          // Optimize comparisons
          comparisons: true,
          // Optimize sequences
          sequences: true,
          // Optimize properties
          properties: true,
        },
        mangle: {
          // Mangle property names for smaller bundles
          properties: {
            regex: /^_/,
          },
        },
        format: {
          // Remove comments
          comments: false,
        },
      } : undefined,

      // Chunk size warnings
      chunkSizeWarningLimit: 1000,

      // CSS code splitting
      cssCodeSplit: true,

      // Optimize CSS
      cssMinify: isProduction,

      // Report compressed size
      reportCompressedSize: isProduction,

      rollupOptions: {
        output: {
          // Enhanced manual chunk splitting for better caching
          manualChunks: {
            // React ecosystem
            'react-vendor': ['react', 'react-dom'],
            'react-router': ['react-router-dom'],

            // UI libraries
            'ui-vendor': [
              '@headlessui/react',
              '@heroicons/react',
              'lucide-react'
            ],

            // State management and utilities
            'utils-vendor': ['zustand', 'clsx', 'class-variance-authority'],

            // Charts and visualization (if used)
            ...(isProduction && {
              'charts-vendor': ['recharts'],
            })
          },

          // Optimize chunk file names
          chunkFileNames: (chunkInfo) => {
            const facadeModuleId = chunkInfo.facadeModuleId
            if (facadeModuleId) {
              const fileName = path.basename(facadeModuleId, path.extname(facadeModuleId))
              return `chunks/${fileName}-[hash].js`
            }
            return 'chunks/[name]-[hash].js'
          },

          // Optimize asset file names
          assetFileNames: (assetInfo) => {
            const info = assetInfo.name?.split('.') || []
            const ext = info[info.length - 1]

            if (/\.(png|jpe?g|svg|gif|tiff|bmp|ico)$/i.test(assetInfo.name || '')) {
              return `images/[name]-[hash].${ext}`
            }
            if (/\.(woff2?|eot|ttf|otf)$/i.test(assetInfo.name || '')) {
              return `fonts/[name]-[hash].${ext}`
            }
            return `assets/[name]-[hash].${ext}`
          },
        },
      },
    },

    // Optimize dependencies
    optimizeDeps: {
      include: [
        'react',
        'react-dom',
        'react-router-dom',
        'zustand',
        'clsx',
        'class-variance-authority',
        'lucide-react',
      ],
      exclude: [
        // Exclude large dependencies that should be loaded on demand
      ],
    },

    // CSS preprocessing
    css: {
      // CSS modules configuration
      modules: {
        localsConvention: 'camelCase',
      },
    },

    // Define global constants
    define: {
      __APP_VERSION__: JSON.stringify(process.env.npm_package_version || '1.0.0'),
      __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
      __DEV__: JSON.stringify(isDevelopment),
    },

    // Environment variables
    envPrefix: ['VITE_', 'REACT_APP_'],

    // Preview server (for production builds)
    preview: {
      port: 3000,
      strictPort: true,
      open: true,
    },
  }
})