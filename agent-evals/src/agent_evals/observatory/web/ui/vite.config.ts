import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "path";

export default defineConfig({
  plugins: [
    react({
      babel: {
        plugins: [["babel-plugin-react-compiler", { runtimeModule: "react-compiler-runtime" }]],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
      "react/compiler-runtime": path.resolve(__dirname, "node_modules/react-compiler-runtime/dist/index.js"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../static"),
    emptyOutDir: true,
    rollupOptions: {
      output: {
        manualChunks: {
          'react-vendor': ['react', 'react-dom', 'react-router-dom'],
          'charting': ['chart.js', 'react-chartjs-2'],
          'animation': ['framer-motion'],
          'table': ['@tanstack/react-table', '@tanstack/react-virtual'],
        },
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://localhost:8765",
    },
  },
});
