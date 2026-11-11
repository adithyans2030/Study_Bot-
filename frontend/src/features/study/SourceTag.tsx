import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import type { SourceRef } from "./api"

const SB_BORDER = "var(--border)"
const SB_MUTED = "var(--muted-foreground)"

/** Shows which knowledge node a generated quiz question or flashcard was grounded in - the same
 * "cite back to something real" contract chat answers already honour via CitationChip. Renders
 * nothing when the model didn't supply (or hallucinated) a valid source, rather than a placeholder. */
export function SourceTag({ source }: { source: SourceRef | null | undefined }) {
  if (!source) return null

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            fontSize: 10,
            fontWeight: 600,
            color: SB_MUTED,
            border: `1px solid ${SB_BORDER}`,
            borderRadius: 100,
            padding: "1px 8px",
            cursor: "default",
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
          }}
        >
          Source: {source.title}
        </span>
      </TooltipTrigger>
      <TooltipContent className="max-w-xs">
        <p className="font-medium">{source.title}</p>
        <p className="text-xs opacity-80">
          {source.type} - {source.source_document}
        </p>
      </TooltipContent>
    </Tooltip>
  )
}
