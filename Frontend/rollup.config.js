import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      output: {
        format: 'esm',
        sourcemap: true,
        module: true // 👈 This is the fix
      }
    }
  }
});
