import { defineConfig, devices } from "@playwright/test";

// The end-to-end tests (README.md): the app at E2E_BASE_URL, started by docker-compose.e2e.yml
// with a fake Gemini. Chromium only; each test signs up its own user, so tests run in parallel.
export default defineConfig({
  testDir: "./tests",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: true,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
