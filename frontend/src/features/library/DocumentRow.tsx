import { AlertTriangle, ExternalLink, Loader2, MoreVertical, RefreshCw, Trash2 } from "lucide-react"
import { FileTypeIcon, fileTypeLabel } from "@/design-system/FileTypeIcon"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { formatRelative, parseServerTimestamp } from "@/lib/format"
import type { LibraryDocument } from "./types"

export function DocumentRow({
  document,
  reindexing,
  onReindex,
  onDelete,
}: {
  document: LibraryDocument
  reindexing: boolean
  onReindex: () => void
  onDelete: () => void
}) {
  return (
    <li className="border-border bg-card flex items-center gap-3 rounded-md border p-3">
      <FileTypeIcon type={document.type} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{document.title}</p>
        <p className="text-muted-foreground mt-0.5 flex flex-wrap items-center gap-x-2 text-xs">
          <span>{fileTypeLabel(document.type)}</span>
          <span aria-hidden>·</span>
          <span>{document.chunks} passages</span>
          <span aria-hidden>·</span>
          <span>Added {formatRelative(parseServerTimestamp(String(document.added)))}</span>
        </p>
        {document.warnings.length > 0 && (
          <p className="text-warning mt-1 flex items-start gap-1 text-xs">
            <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden />
            <span>{document.warnings.join(" ")}</span>
          </p>
        )}
      </div>
      {reindexing ? (
        <Loader2
          className="text-muted-foreground size-4 shrink-0 animate-spin"
          aria-label="Re-processing"
        />
      ) : (
        <DropdownMenu>
          <DropdownMenuTrigger
            className="text-muted-foreground hover:text-foreground hover:bg-muted shrink-0 rounded-md p-1.5"
            aria-label={`More actions for ${document.title}`}
          >
            <MoreVertical className="size-4" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            {document.url && (
              <DropdownMenuItem asChild>
                <a href={document.url} target="_blank" rel="noreferrer">
                  <ExternalLink /> Open on YouTube
                </a>
              </DropdownMenuItem>
            )}
            <DropdownMenuItem onSelect={onReindex}>
              <RefreshCw /> Re-process
            </DropdownMenuItem>
            <DropdownMenuItem variant="destructive" onSelect={onDelete}>
              <Trash2 /> Delete
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      )}
    </li>
  )
}
