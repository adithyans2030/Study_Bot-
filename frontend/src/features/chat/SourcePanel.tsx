import { ExternalLink } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet"
import { FileTypeIcon, fileTypeLabel } from "@/design-system/FileTypeIcon"
import type { Source } from "./types"

/** The source viewer (§6.5). Shows the cited passage's text and where it came from — not a
 * pixel-level PDF page render with a highlighted box: the backend gives a page/slide/timestamp
 * and the exact cited chunk text, not a page image or bounding box (see PLAN.md's frontend
 * rewrite tracker). A YouTube source gets a real deep link to the cited moment instead. */
export function SourcePanel({
  sources,
  activeIndex,
  onActiveIndexChange,
  onClose,
}: {
  sources: Source[]
  activeIndex: number | null
  onActiveIndexChange: (index: number) => void
  onClose: () => void
}) {
  const open = activeIndex !== null && sources.length > 0
  const source = activeIndex !== null ? sources[activeIndex] : null

  return (
    <Sheet open={open} onOpenChange={(next) => !next && onClose()}>
      <SheetContent className="flex w-full flex-col gap-0 sm:max-w-md">
        <SheetHeader className="border-border border-b">
          <div className="flex items-center gap-3">
            {source && <FileTypeIcon type={source.type} />}
            <div className="min-w-0 flex-1">
              <SheetTitle className="truncate">{source?.title}</SheetTitle>
              {source?.location && (
                <p className="text-muted-foreground text-sm">{source.location}</p>
              )}
            </div>
          </div>
        </SheetHeader>

        {sources.length > 1 && (
          <div
            className="border-border flex gap-1 overflow-x-auto border-b p-2"
            role="tablist"
            aria-label="Sources cited in this answer"
          >
            {sources.map((s, i) => (
              <Button
                key={s.n}
                role="tab"
                aria-selected={i === activeIndex}
                variant={i === activeIndex ? "secondary" : "ghost"}
                size="sm"
                onClick={() => onActiveIndexChange(i)}
              >
                [{s.n}]
              </Button>
            ))}
          </div>
        )}

        {source && (
          <div className="flex-1 space-y-4 overflow-y-auto p-4">
            <p className="text-muted-foreground text-xs">{source.header}</p>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{source.snippet}</p>
            {source.url && (
              <Button asChild variant="outline" size="sm">
                <a href={source.url} target="_blank" rel="noreferrer">
                  <ExternalLink /> Play from here on {fileTypeLabel(source.type)}
                </a>
              </Button>
            )}
          </div>
        )}
      </SheetContent>
    </Sheet>
  )
}
