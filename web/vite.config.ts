import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { VitePWA } from "vite-plugin-pwa";

export default defineConfig({
  base: "/DND-calculator/",
  worker: { format: "es" },
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: ["icon.svg"],
      manifest: {
        name: "池中社 DND 战斗计算器",
        short_name: "DND 计算器",
        description: "离线 D&D 5e 2014 攻击结算、构筑比较与战斗时长规划工具",
        theme_color: "#8a6d3b",
        background_color: "#e8dcc0",
        display: "standalone",
        start_url: "/DND-calculator/",
        scope: "/DND-calculator/",
        lang: "zh-CN",
        icons: [{ src: "icon.svg", sizes: "any", type: "image/svg+xml", purpose: "any maskable" }],
      },
      workbox: {
        globPatterns: ["**/*.{js,mjs,css,html,svg,json,wasm,zip,whl}"],
        maximumFileSizeToCacheInBytes: 30 * 1024 * 1024,
        navigateFallback: "/DND-calculator/index.html",
      },
    }),
  ],
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    exclude: ["e2e/**", "node_modules/**", "dist/**"],
    coverage: {
      provider: "v8",
      // React interaction coverage is enforced by the desktop/mobile Playwright suite.
      // Unit thresholds apply to reusable configuration and expectation business modules.
      include: ["src/config.ts", "src/components/Results.tsx"],
      exclude: ["src/**/*.test.ts", "src/**/*.test.tsx"],
      thresholds: { lines: 80, statements: 80, functions: 80, branches: 70 },
    },
  },
});
