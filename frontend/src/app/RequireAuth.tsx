import { Loader2 } from "lucide-react"
import { Navigate, Outlet, useLocation } from "react-router-dom"
import { useAuthStatus } from "@/features/auth/hooks"
import { OfflineState } from "./OfflineState"

/** Protects a route subtree. Redirects to sign-in (or to first-run setup) rather than ever
 * rendering a page that would immediately 401 — and remembers where the student was headed, so
 * signing in returns them there instead of dumping them on the dashboard. An unreachable API is
 * shown as "offline", not silently redirected to a sign-in page that can't load either. */
export function RequireAuth() {
  const status = useAuthStatus()
  const location = useLocation()

  if (status.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Loader2 className="text-muted-foreground size-6 animate-spin" aria-label="Loading" />
      </div>
    )
  }

  if (status.isError) {
    return <OfflineState onRetry={() => status.refetch()} />
  }

  if (!status.data?.user) {
    const to = status.data && !status.data.has_users ? "/register" : "/login"
    return <Navigate to={to} state={{ from: location.pathname }} replace />
  }

  return <Outlet />
}
