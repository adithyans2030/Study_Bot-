import { Check, Copy, Info, Search } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { speakable } from "@/lib/rich"
import { MessageContent } from "./MessageContent"
import { SourcesRow } from "./SourcesRow"
import type { AnswerMeta, Source } from "./types"

export interface AnswerBubbleData {
  content: string
  sources: Source[]
  meta: Partial<AnswerMeta> | null
  streaming: boolean
  searchQuery?: string | null
}

/** One assistant answer, whether it's a saved message played back from history or the live
 * in-flight one still streaming — both are normalized to `AnswerBubbleData` so this is the only
 * place answer rendering happens. Full-width, no bubble, like a document (§6.4): long study
 * answers read better that way than squeezed into a chat-bubble width. */
export function AnswerBubble({
  data,
  onCiteClick,
}: {
  data: AnswerBubbleData
  onCiteClick: (n: number) => void
}) {
  const [copied, setCopied] = useState(false)
  const refused = data.meta?.refused ?? false
  const waitingForSources = data.streaming && data.sources.length === 0 && !data.content
  const waitingForText = data.streaming && data.sources.length > 0 && !data.content

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(speakable(data.content) || data.content)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can be denied; nothing to recover, the text is still selectable by hand.
    }
  }

  return (
    <div className="space-y-2" aria-live={data.streaming ? "polite" : undefined}>
      {data.searchQuery && (
        <p className="text-muted-foreground flex items-center gap-1.5 text-xs">
          <Search className="size-3.5" /> Searched for: “{data.searchQuery}”
        </p>
      )}

      {waitingForSources ? (
        <ThinkingLine text="Searching your notes…" />
      ) : waitingForText ? (
        <ThinkingLine text="Writing answer…" />
      ) : refused ? (
        <div className="border-border bg-muted/50 flex gap-2 rounded-md border p-3 text-sm">
          <Info className="text-muted-foreground mt-0.5 size-4 shrink-0" />
          <p>{data.content}</p>
        </div>
      ) : (
        <MessageContent text={data.content} sources={data.sources} onCiteClick={onCiteClick} />
      )}

      {!refused && <SourcesRow sources={data.sources} onOpen={onCiteClick} />}

      {(data.meta?.invalid_citations ?? 0) > 0 && (
        <p className="text-muted-foreground text-xs">
          Note: this answer referenced a source number that doesn't exist; ignore any citation not
          listed above.
        </p>
      )}

      {!data.streaming && data.content && (
        <Button variant="ghost" size="sm" onClick={copy} className="text-muted-foreground -ml-2">
          {copied ? <Check className="text-success" /> : <Copy />}
          {copied ? "Copied" : "Copy"}
        </Button>
      )}
    </div>
  )
}

function ThinkingLine({ text }: { text: string }) {
  return (
    <p className="text-muted-foreground flex items-center gap-2 text-sm">
      <span className="flex gap-0.5">
        <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full [animation-delay:-0.3s]" />
        <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full [animation-delay:-0.15s]" />
        <span className="bg-muted-foreground size-1.5 animate-bounce rounded-full" />
      </span>
      {text}
    </p>
  )
}
