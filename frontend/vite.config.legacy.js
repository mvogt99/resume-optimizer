import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react({ include: '**/*.{js,jsx}' })],
  define: {
    'import.meta.env.VITE_CLOUDLIFT_ENV': JSON.stringify('legacy'),
  },
  server: {
    port: 3010,
    proxy: { '/api': 'http://localhost:5010' },
  },
  build: { outDir: 'build' },
});
