import { StrictMode } from "react"
import { createRoot } from "react-dom/client"
import { RouterProvider } from "react-router-dom"
import { AppProviders } from "@/app/providers"
import { router } from "@/app/router"
import "./index.css"

const root = createRoot(document.getElementById("root")!)

function render() {
  root.render(
    <StrictMode>
      <AppProviders>
        <RouterProvider router={router} />
      </AppProviders>
    </StrictMode>,
  )
}

if (import.meta.env.DEV) {
  // Logs accessibility violations to the console as you work, in dev only — never shipped, and
  // never a substitute for the automated axe checks in the Playwright suite (Milestone G) or a
  // real screen reader pass, just a fast first-line check while building each screen.
  const [{ default: axe }, React, ReactDOM] = await Promise.all([
    import("@axe-core/react"),
    import("react"),
    import("react-dom"),
  ])
  axe(React, ReactDOM, 1000)
}

render()
