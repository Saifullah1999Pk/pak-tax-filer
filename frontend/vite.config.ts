/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  // The browser calls /api on the frontend's own origin and Vite forwards it to the backend
  // container, so the session cookie works without cross-origin setup (feature 002, research R8).
  server: {
    proxy: {
      "/api": "http://backend:8000",
    },
  },
  // Vitest shares Vite's config (research R4); jsdom lets tests render components without a browser.
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test-setup.ts"],
  },
});
