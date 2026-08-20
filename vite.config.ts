import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

// GitHub Pages 하위 경로(/<repo>/)에서도 그대로 동작하도록 상대경로로 뺀다.
export default defineConfig({
  base: './',
  plugins: [react(), tailwindcss()],
  build: { outDir: 'dist', assetsDir: 'assets' },
});
