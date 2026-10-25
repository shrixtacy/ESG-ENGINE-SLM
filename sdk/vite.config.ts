import { defineConfig } from 'vite';
import dts from 'vite-plugin-dts';
import { resolve } from 'path';

export default defineConfig({
  plugins: [
    dts({ include: ['src'] }),
  ],
  build: {
    lib: {
      entry: resolve(__dirname, 'src/index.ts'),
      name: 'ESGPilot',
      formats: ['es', 'cjs', 'umd'],
      fileName: (format) => {
        if (format === 'es') return 'sdk.esm.js';
        if (format === 'cjs') return 'sdk.cjs.js';
        return 'sdk.umd.js';
      },
    },
    rollupOptions: {
      // Do NOT externalize lit — bundle everything for the drop-in script
      external: [],
    },
    // Target < 80 KB gzip per BUILD_SPEC
    minify: 'terser',
    target: 'es2020',
  },
});
