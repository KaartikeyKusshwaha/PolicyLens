import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Auto-detect environment: Docker uses 'backend' hostname, local uses 'localhost'
const isDocker = process.env.DOCKER_ENV === 'true'
const apiTarget = process.env.VITE_API_URL || (isDocker ? 'http://backend:8000' : 'http://localhost:8000')

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/api': {
        target: apiTarget,
        changeOrigin: true,
        secure: false,
      }
    },
    // Improve HMR stability
    hmr: {
      overlay: true,
    }
  },
  // Optimize dependencies for faster dev server startup
  optimizeDeps: {
    include: ['react', 'react-dom', 'react-router-dom']
  }
})
