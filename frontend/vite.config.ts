
import { createLogger, defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import { fileURLToPath } from 'node:url';

const logger = createLogger();
const originalError = logger.error;

logger.error = (message, options) =>
  originalError(
    message.replace(/([?&]number=)[^&\s]*/gi, '$1[omitido]'),
    options
  );

export default defineConfig({
  customLogger: logger,

  plugins: [
    react(),
    tailwindcss()
  ],

  server: {
    port: 5173,
    strictPort: true,

    // Dominio autorizado de Cloudflare
  allowedHosts: [
  'gratuit-okay-flying-thanksgiving.trycloudflare.com'
  ],

    fs: {
      strict: true,
      allow: [
        fileURLToPath(new URL('.', import.meta.url))
      ],
      deny: [
        '**/.git/**',
        '**/.env*',
        '**/data/**',
        '**/*.sqlite*',
        '**/*.zip',
        '**/*.log',
        '**/*.pem',
        '**/*.key'
      ]
    },

    headers: {
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer'
    },

    watch: {
      ignored: [
        '**/tests/**',
        '**/*.tsbuildinfo'
      ]
    },

    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  },

  preview: {
    port: 4173,

    headers: {
      'X-Frame-Options': 'DENY',
      'Referrer-Policy': 'no-referrer'
    },

    proxy: {
      '/api': 'http://127.0.0.1:8000'
    }
  },

  build: {
    target: 'es2020'
  }
});
