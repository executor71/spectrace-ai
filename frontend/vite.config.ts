import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/actuator': 'http://backend:8080',
      '/ai-health': {
        target: 'http://ai-service:8000',
        rewrite: (path) => path.replace(/^\/ai-health/, ''),
      },
    },
  },
})
