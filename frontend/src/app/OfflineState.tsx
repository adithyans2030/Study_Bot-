import { RefreshCw, WifiOff } from "lucide-react"

/** StudyBot runs on your own PC — if the API can't be reached, the PC (or the server on it) is
 * probably off, not "something is broken." Reused by the PWA's offline screen in Milestone F.
 *
 * A plain `<button>`, not shadcn's `Button`, on purpose: this and NotFoundPage are reachable from
 * RequireAuth/RootRedirect, which load eagerly on every route — pulling in Button's cva variants
 * and Radix Slot here would mean every single visitor downloads them before painting anything,
 * just for two screens simple enough not to need them. */
export function OfflineState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center">
      <div className="bg-muted flex size-12 items-center justify-center rounded-full">
        <WifiOff className="text-muted-foreground size-6" aria-hidden />
      </div>
      <div className="space-y-1.5">
        <h1 className="text-xl font-semibold">Can't reach StudyBot</h1>
        <p className="text-muted-foreground max-w-sm text-sm">
          The PC running StudyBot might be off, asleep, or on a different network. Your chats and
          documents are safe — this will reconnect as soon as it's reachable again.
        </p>
      </div>
      <button
        type="button"
        onClick={onRetry}
        className="border-input bg-background hover:bg-muted inline-flex h-8 items-center gap-1.5 rounded-md border px-3 text-sm font-medium transition-colors"
      >
        <RefreshCw className="size-4" /> Try again
      </button>
    </div>
  )
}
