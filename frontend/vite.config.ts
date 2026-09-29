import path from "node:path"
import tailwindcss from "@tailwindcss/vite"
import react from "@vitejs/plugin-react"
import { defineConfig } from "vite"
import { VitePWA } from "vite-plugin-pwa"

// The real StudyBot backend already exists and is tested (258 pytest tests, a 38-check
// real-browser smoke test) — the dev server proxies /api straight to it instead of mocking a
// separate contract. Because the browser only ever talks to this dev server's own origin,
// StudyBot's session cookie (HttpOnly, SameSite=Lax) and its Origin-check CSRF middleware behave
// exactly as they do in production; no CORS configuration needed on either side.
// Override with STUDYBOT_DEV_BACKEND to point at a throwaway backend (e.g. a fresh STUDYBOT_HOME
// on another port) without touching this file — handy since the real one's registration is closed.
const BACKEND = process.env.STUDYBOT_DEV_BACKEND ?? "http://127.0.0.1:8000"

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    VitePWA({
      registerType: "autoUpdate",
      // The manifest and icons are the same ones the plain-JS dashboard shipped — no redesign
      // needed, just updated to this project's colors and paths.
      manifest: {
        id: "/",
        name: "StudyBot",
        short_name: "StudyBot",
        description: "Ask questions about your own notes, slides and lectures. Free and private.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        orientation: "any",
        background_color: "#f5f0e8",
        theme_color: "#1e4d3f",
        categories: ["education", "productivity"],
        icons: [
          { src: "/icons/icon-192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icons/icon-512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          {
            src: "/icons/icon-maskable-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        globPatterns: ["**/*.{js,css,html,woff2,png,svg,ico}"],
        // The one non-negotiable rule, carried over from the plain-JS dashboard's hand-written
        // service worker: never cache /api/ — auth state, chat streams and every user's own data
        // must always go to the real server, never a stale cached response.
        navigateFallbackDenylist: [/^\/api\//],
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.startsWith("/api/"),
            handler: "NetworkOnly",
          },
        ],
      },
      devOptions: { enabled: false }, // the dev server already has hot reload; a SW would just fight it
    }),
  ],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
  build: {
    // Built into the backend's own package (not a sibling directory reached at runtime) so a
    // deployed backend is self-contained — it never needs the frontend's source or node_modules
    // present, only this one generated folder. Not committed (see .gitignore); scripts/setup.ps1
    // runs `npm run build` to produce it, the same way it already sets up the Python venv.
    outDir: path.resolve(import.meta.dirname, "../backend/app/dist"),
    emptyOutDir: true,
  },
  server: {
    // This machine resolves "localhost" to ::1 (IPv6) only, which most tools (curl, Playwright)
    // don't try by default — bind the literal IPv4 loopback so http://127.0.0.1:<port> always works.
    host: "127.0.0.1",
    proxy: {
      // changeOrigin must stay off: the backend's CSRF middleware compares the browser's Origin
      // header against the request's Host header (see app/core/security.py), and changeOrigin
      // rewrites Host to the proxy target (127.0.0.1:8000) while leaving Origin as the dev
      // server's own (127.0.0.1:5173) â€” the mismatch gets every POST/PUT/PATCH/DELETE rejected
      // as "Cross-site request blocked." Not needed anyway: the target isn't virtual-hosted.
      "/api": { target: BACKEND },
    },
  },
})
