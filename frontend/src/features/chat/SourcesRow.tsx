import { FileTypeIcon } from "@/design-system/FileTypeIcon"
import type { Source } from "./types"

export function SourcesRow({
  sources,
  onOpen,
}: {
  sources: Source[]
  onOpen: (index: number) => void
}) {
  if (sources.length === 0) return null

  return (
    <div className="mt-3 flex flex-wrap gap-2" role="list" aria-label="Sources">
      {sources.map((source, i) => (
        <button
          key={source.n}
          role="listitem"
          type="button"
          onClick={() => onOpen(i)}
          className="border-border bg-card hover:bg-muted focus-visible:ring-ring flex items-center gap-2 rounded-md border px-2 py-1.5 text-left text-xs transition-colors focus-visible:ring-2 focus-visible:outline-none"
        >
          <FileTypeIcon type={source.type} className="size-6 rounded-sm" />
          <span className="max-w-[12rem] truncate">
            {source.title}
            {source.location ? ` · ${source.location}` : ""}
          </span>
        </button>
      ))}
    </div>
  )
}
