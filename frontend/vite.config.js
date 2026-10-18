import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const proxy = Object.fromEntries(
  ["/api", "/docs", "/openapi.json", "/redoc"].map((path) => [path, "http://127.0.0.1:8000"]),
);

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 3000,
    strictPort: true,
    proxy,
  },
  preview: {
    host: "127.0.0.1",
    port: 3000,
    proxy,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: "./src/test-setup.js",
  },
});
