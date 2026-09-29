import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vitest/config"

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: true,
    // A fresh jsdom per test file was ~78% of total run time once the suite grew past a handful
    // of files (Vitest's own advice for exactly this). Each test still gets its own module
    // registry / mocked globals via vi.stubGlobal + afterEach cleanup, just not its own jsdom.
    isolate: false,
  },
})
