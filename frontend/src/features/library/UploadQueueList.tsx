import { AlertCircle, CheckCircle2, Loader2, X } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import { JobWatcher } from "@/features/jobs/JobWatcher"
import { stageLabel } from "./stageLabel"
import type { UploadItem } from "./useUploadQueue"

export function UploadQueueList({
  items,
  onCancel,
  onDismiss,
  onJobUpdate,
}: {
  items: UploadItem[]
  onCancel: (localId: string) => void
  onDismiss: (localId: string) => void
  onJobUpdate: (localId: string, job: import("./types").Job) => void
}) {
  if (items.length === 0) return null

  return (
    <ul className="space-y-2" aria-label="Uploads">
      {items.map((item) => (
        <li
          key={item.localId}
          className="border-border bg-card flex items-center gap-3 rounded-md border p-3"
        >
          {item.phase === "processing" && item.job && (
            <JobWatcher jobId={item.job.id} onUpdate={(job) => onJobUpdate(item.localId, job)} />
          )}

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-medium">{item.fileName}</p>
            {item.phase === "uploading" && (
              <Progress value={item.progress * 100} className="mt-1.5 h-1.5" />
            )}
            {item.phase === "processing" && (
              <p className="text-muted-foreground mt-0.5 text-xs">
                {stageLabel(item.job?.stage ?? "starting")}
              </p>
            )}
            {item.phase === "failed" && (
              <p className="text-destructive mt-0.5 text-xs">
                {item.error ?? item.job?.error ?? "Something went wrong."}
              </p>
            )}
            {item.phase === "done" && (
              <p className="text-muted-foreground mt-0.5 text-xs">Added to your library</p>
            )}
          </div>

          <div className="flex shrink-0 items-center gap-1">
            {(item.phase === "uploading" || item.phase === "processing") && (
              <>
                <Loader2 className="text-muted-foreground size-4 animate-spin" aria-hidden />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Cancel uploading ${item.fileName}`}
                  onClick={() => onCancel(item.localId)}
                >
                  <X />
                </Button>
              </>
            )}
            {item.phase === "done" && <CheckCircle2 className="text-success size-5" aria-hidden />}
            {item.phase === "failed" && (
              <>
                <AlertCircle className="text-destructive size-5" aria-hidden />
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Dismiss ${item.fileName}`}
                  onClick={() => onDismiss(item.localId)}
                >
                  <X />
                </Button>
              </>
            )}
          </div>
        </li>
      ))}
    </ul>
  )
}
