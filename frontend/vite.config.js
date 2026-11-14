import { defineConfig } from 'vite';
import { svelte } from '@sveltejs/vite-plugin-svelte';

// En desarrollo (npm run dev) Vite reenvía /api y /ws al backend.
// En Docker lo hace nginx (nginx.conf). Así el frontend siempre usa rutas
// relativas y no hace falta CORS.
export default defineConfig({
  plugins: [svelte()],
  server: {
    proxy: {
      '/api': 'http://localhost:8000',
      '/ws': { target: 'ws://localhost:8000', ws: true },
    },
  },
});
