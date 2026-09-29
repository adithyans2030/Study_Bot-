import { Send, Square } from "lucide-react"
import { useEffect, useRef } from "react"
import { Button } from "@/components/ui/button"

const MAX_LENGTH = 2000
const WARN_AT = 1800

export function Composer({
  value,
  onChange,
  onSend,
  onStop,
  sending,
  disabled,
  placeholder,
}: {
  value: string
  onChange: (value: string) => void
  onSend: () => void
  onStop: () => void
  sending: boolean
  disabled?: boolean
  placeholder: string
}) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    const el = textareaRef.current
    if (!el) return
    el.style.height = "auto"
    el.style.height = `${Math.min(el.scrollHeight, 8 * 24)}px` // ~8 lines, then it scrolls
  }, [value])

  const submit = () => {
    if (sending || disabled || !value.trim()) return
    onSend()
  }

  return (
    <div className="border-border bg-background border-t p-3">
      <div className="border-input focus-within:ring-ring/50 focus-within:border-ring flex items-end gap-2 rounded-lg border px-3 py-2 focus-within:ring-3">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => onChange(e.target.value.slice(0, MAX_LENGTH))}
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault()
              submit()
            } else if (e.key === "Escape" && sending) {
              onStop()
            }
          }}
          placeholder={placeholder}
          disabled={disabled}
          rows={1}
          className="placeholder:text-muted-foreground max-h-48 flex-1 resize-none bg-transparent text-sm outline-none disabled:opacity-50"
        />
        {sending ? (
          <Button
            type="button"
            size="icon"
            variant="secondary"
            onClick={onStop}
            aria-label="Stop generating"
          >
            <Square className="fill-current" />
          </Button>
        ) : (
          <Button
            type="button"
            size="icon"
            onClick={submit}
            disabled={disabled || !value.trim()}
            aria-label="Send"
          >
            <Send />
          </Button>
        )}
      </div>
      <div className="mt-1 flex items-center justify-between px-1">
        <p className="text-muted-foreground text-xs">
          <kbd className="bg-muted rounded px-1 py-0.5 font-sans">Enter</kbd> to send ·{" "}
          <kbd className="bg-muted rounded px-1 py-0.5 font-sans">Shift+Enter</kbd> for a new line
        </p>
        {value.length >= WARN_AT && (
          <p className="text-muted-foreground text-xs">
            {value.length}/{MAX_LENGTH}
          </p>
        )}
      </div>
    </div>
  )
}
