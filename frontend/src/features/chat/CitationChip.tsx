import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { Source } from "./types"

/** The "trust through evidence" principle made clickable: every citation is a small, focusable
 * chip in the evidence color, not a bare bracketed number. A hover/focus preview shows where it
 * came from before you commit to opening the full source panel. */
export function CitationChip({
  n,
  source,
  onClick,
}: {
  n: number
  source: Source | undefined
  onClick: () => void
}) {
  const label = source
    ? `Source ${n}: ${source.title}${source.location ? `, ${source.location}` : ""}`
    : `Source ${n}`

  const button = (
    <button
      type="button"
      onClick={onClick}
      disabled={!source}
      aria-label={label}
      className="bg-evidence/15 text-evidence hover:bg-evidence/25 focus-visible:ring-ring mx-0.5 inline-flex size-4 items-center justify-center rounded-sm align-super text-[10px] font-medium transition-colors focus-visible:ring-2 focus-visible:outline-none disabled:opacity-50"
    >
      {n}
    </button>
  )

  if (!source) return button

  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-medium">
          {source.title}
          {source.location ? ` · ${source.location}` : ""}
        </p>
        <p className="text-xs opacity-80">{source.snippet}</p>
      </TooltipContent>
    </Tooltip>
  )
}
