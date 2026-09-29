import { Loader2 } from "lucide-react"
import { Navigate } from "react-router-dom"
import { useAuthStatus } from "@/features/auth/hooks"
import { OfflineState } from "./OfflineState"

/** "/" has no content of its own — it sends you to the dashboard, sign-in, or first-run setup. */
export function RootRedirect() {
  const status = useAuthStatus()

  if (status.isPending) {
    return (
      <div className="flex min-h-svh items-center justify-center">
        <Loader2 className="text-muted-foreground size-6 animate-spin" aria-label="Loading" />
      </div>
    )
  }

  if (status.isError) return <OfflineState onRetry={() => status.refetch()} />
  if (status.data.user) return <Navigate to="/app" replace />
  if (!status.data.has_users) return <Navigate to="/register" replace />
  return <Navigate to="/login" replace />
}
