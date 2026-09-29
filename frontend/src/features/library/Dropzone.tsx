import { UploadCloud } from "lucide-react"
import { useId, useRef, useState } from "react"

const ACCEPT = ".pdf,.pptx,.docx"

/** Hand-rolled rather than a dropzone library: this is one of the two budget-gated routes
 * (§10 — "login and dashboard"), and a real drag-and-drop zone is a handful of DOM events, not
 * worth a dependency for. Accepts multiple files; the caller decides what to do with each. */
export function Dropzone({
  onFiles,
  disabled,
  disabledHint,
}: {
  onFiles: (files: File[]) => void
  disabled?: boolean
  /** Shown in place of the normal hint when disabled, so "nothing happens when I click/drop"
   * always has a visible reason (e.g. "Name a collection first") rather than looking broken. */
  disabledHint?: string
}) {
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)
  const inputId = useId()

  const accept = (files: FileList | null) => {
    if (files && files.length) onFiles(Array.from(files))
  }

  return (
    <div
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      onClick={() => !disabled && inputRef.current?.click()}
      onKeyDown={(e) => {
        if (!disabled && (e.key === "Enter" || e.key === " ")) {
          e.preventDefault()
          inputRef.current?.click()
        }
      }}
      onDragOver={(e) => {
        e.preventDefault()
        if (!disabled) setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault()
        setDragging(false)
        if (!disabled) accept(e.dataTransfer.files)
      }}
      className={`flex cursor-pointer flex-col items-center gap-2 rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
        dragging ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"
      } ${disabled ? "pointer-events-none opacity-50" : ""}`}
    >
      <UploadCloud className="text-muted-foreground size-8" aria-hidden />
      <p className="text-sm font-medium">
        Drop your notes here, or <span className="text-primary">browse</span>
      </p>
      <p className="text-muted-foreground text-xs">
        {disabled && disabledHint ? disabledHint : "PDF, Word or PowerPoint, up to 100 MB each"}
      </p>
      <label htmlFor={inputId} className="sr-only">
        Choose files to upload
      </label>
      <input
        id={inputId}
        ref={inputRef}
        type="file"
        multiple
        accept={ACCEPT}
        disabled={disabled}
        className="sr-only"
        onChange={(e) => {
          accept(e.target.files)
          e.target.value = "" // lets choosing the same file again re-trigger onChange
        }}
      />
    </div>
  )
}
