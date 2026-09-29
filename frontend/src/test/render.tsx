import { QueryClient } from "@tanstack/react-query"
import { render } from "@testing-library/react"
import type { ReactElement } from "react"
import { MemoryRouter } from "react-router-dom"
import { AppProviders } from "@/app/providers"

/** Wraps a component with the app's real provider tree (so anything using useTheme/Tooltip/toast
 * works exactly as it does in the app, with no separate provider stack to drift out of sync) plus
 * a router. Uses a fresh QueryClient per render — `retry: false` so a mocked-failed request fails
 * immediately instead of retrying and timing out the test — so one test's cache never leaks into
 * the next. */
export function renderWithProviders(ui: ReactElement, { route = "/" }: { route?: string } = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <AppProviders queryClient={queryClient}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </AppProviders>,
  )
}
