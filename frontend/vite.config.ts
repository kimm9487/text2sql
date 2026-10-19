import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// dev: http://localhost:5173 (API 는 8000 으로 프록시)
// build: ../backend/static 에 출력 → FastAPI 가 같이 서빙
export default defineConfig({
  plugins: [react()],
  resolve: { dedupe: ['react', 'react-dom'] },
  server: {
    proxy: { '/api': 'http://localhost:8000' },
  },
  build: {
    outDir: '../backend/static',
    emptyOutDir: true,
    chunkSizeWarningLimit: 1200,
    rollupOptions: {
      output: { manualChunks: { echarts: ['echarts', 'echarts-for-react'] } },
    },
  },
})
