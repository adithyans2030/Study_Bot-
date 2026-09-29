import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { ThemeProvider } from "next-themes"
import { useState } from "react"
import { Toaster } from "@/components/ui/sonner"
import { TooltipProvider } from "@/components/ui/tooltip"

/** Root providers: theming (system by default, manual override persisted by next-themes), server
 * state (TanStack Query — see lib/api.ts for the client), tooltips, and toasts. Kept in one place
 * so tests can wrap a component the same way the app does (`queryClient` is only ever overridden
 * by src/test/render.tsx, so a mocked-failed request in a test doesn't retry and time out). */
export function AppProviders({
  children,
  queryClient: providedClient,
}: {
  children: React.ReactNode
  queryClient?: QueryClient
}) {
  const [ownClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: 1,
            refetchOnWindowFocus: false,
          },
        },
      }),
  )
  const queryClient = providedClient ?? ownClient

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
        <TooltipProvider delayDuration={300}>
          {children}
          <Toaster />
        </TooltipProvider>
      </ThemeProvider>
    </QueryClientProvider>
  )
}
