import { defineConfig, devices } from "@playwright/test";

const environment = (globalThis as {
  process?: { env?: { CI?: string; PLAYWRIGHT_USE_SYSTEM_CHROME?: string } };
}).process?.env;
const isCI = Boolean(environment?.CI);
const browserChannel = environment?.PLAYWRIGHT_USE_SYSTEM_CHROME ? { channel: "chrome" as const } : {};

export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: isCI ? 1 : 0,
  reporter: isCI ? "github" : "list",
  use: {
    baseURL: "http://127.0.0.1:4173/DND-calculator/",
    trace: "retain-on-failure",
  },
  projects: [
    { name: "desktop-chromium", use: { ...devices["Desktop Chrome"], ...browserChannel } },
    { name: "mobile-chromium", use: { ...devices["Pixel 7"], ...browserChannel } },
  ],
  webServer: {
    command: "pnpm preview --host 127.0.0.1 --port 4173",
    url: "http://127.0.0.1:4173/DND-calculator/",
    reuseExistingServer: !isCI,
  },
});
