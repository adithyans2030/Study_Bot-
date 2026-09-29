import { FileText, Presentation, SquarePlay } from "lucide-react"
import type { DocumentType } from "@/features/library/types"

// lucide-react has no brand/logo icons (by design, from this major version on) — SquarePlay
// stands in for "video" rather than a YouTube logo.
const STYLE: Record<DocumentType, { icon: typeof FileText; className: string; label: string }> = {
  pdf: { icon: FileText, className: "bg-red-500/15 text-red-600 dark:text-red-400", label: "PDF" },
  docx: {
    icon: FileText,
    className: "bg-blue-500/15 text-blue-600 dark:text-blue-400",
    label: "Word",
  },
  pptx: {
    icon: Presentation,
    className: "bg-orange-500/15 text-orange-600 dark:text-orange-400",
    label: "PowerPoint",
  },
  youtube: {
    icon: SquarePlay,
    className: "bg-red-500/15 text-red-600 dark:text-red-400",
    label: "YouTube",
  },
}

export function FileTypeIcon({ type, className = "" }: { type: DocumentType; className?: string }) {
  const { icon: Icon, className: colorClass, label } = STYLE[type]
  return (
    <div
      className={`flex size-9 shrink-0 items-center justify-center rounded-md ${colorClass} ${className}`}
      aria-label={label}
    >
      <Icon className="size-4.5" />
    </div>
  )
}

export function fileTypeLabel(type: DocumentType): string {
  return STYLE[type].label
}
