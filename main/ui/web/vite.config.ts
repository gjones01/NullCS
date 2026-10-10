import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT_DIR = resolve(dirname(fileURLToPath(import.meta.url)));

export default defineConfig({
  root: ROOT_DIR,
  plugins: [react()],
  publicDir: false, // The focused client does not ship the old videos, samples, or marketing assets.
  server: {
    port: 5173,
    watch: { ignored: ["**/src-tauri/**"] },
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
      },
    },
  },
});
