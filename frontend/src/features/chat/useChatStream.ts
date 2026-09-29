import { useCallback, useRef, useState } from "react"
import { ApiError } from "@/lib/api"
import { parseJSON, readSSE } from "@/lib/sse"
import type {
  ConversationEventData,
  DoneEventData,
  ErrorEventData,
  QueryEventData,
  Source,
  SourcesEventData,
  TokenEventData,
} from "./types"

export interface LiveAnswer {
  searchQuery: string | null // set only when the question was rewritten as a follow-up
  sources: Source[]
  text: string
  done: boolean
  meta: Omit<DoneEventData, "text"> | null
  error: string | null
}

const EMPTY_ANSWER: LiveAnswer = {
  searchQuery: null,
  sources: [],
  text: "",
  done: false,
  meta: null,
  error: null,
}

/** Drives one `POST /api/chat` exchange. A plain hook rather than a TanStack Query mutation: the
 * interesting part isn't "pending vs success" but a sequence of partial states arriving over
 * several seconds (search query, then sources, then each token, then the final cleaned text) —
 * exactly what `readSSE` was built for. */
export function useChatStream() {
  const [liveUser, setLiveUser] = useState<string | null>(null)
  const [liveAnswer, setLiveAnswer] = useState<LiveAnswer>(EMPTY_ANSWER)
  const [sending, setSending] = useState(false)
  const controllerRef = useRef<AbortController | null>(null)

  const send = useCallback(
    async (
      question: string,
      options: { collections?: string[]; conversationId?: number | null },
      onConversation?: (data: ConversationEventData) => void,
      onDone?: (data: DoneEventData, sources: Source[]) => void,
    ) => {
      const controller = new AbortController()
      controllerRef.current = controller
      setLiveUser(question)
      setLiveAnswer(EMPTY_ANSWER)
      setSending(true)

      try {
        const response = await fetch("/api/chat", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          signal: controller.signal,
          body: JSON.stringify({
            question,
            collections: options.collections ?? null,
            conversation_id: options.conversationId ?? null,
          }),
        })
        if (!response.ok) {
          const body = await response.json().catch(() => null)
          const message =
            body && typeof body.detail === "string"
              ? body.detail
              : `Request failed (${response.status}).`
          throw new ApiError(response.status, message)
        }

        let sources: Source[] = []
        for await (const frame of readSSE(response)) {
          switch (frame.event) {
            case "conversation":
              onConversation?.(parseJSON<ConversationEventData>(frame))
              break
            case "query":
              setLiveAnswer((prev) => ({
                ...prev,
                searchQuery: parseJSON<QueryEventData>(frame).text,
              }))
              break
            case "sources":
              sources = parseJSON<SourcesEventData>(frame)
              setLiveAnswer((prev) => ({ ...prev, sources }))
              break
            case "token":
              setLiveAnswer((prev) => ({
                ...prev,
                text: prev.text + parseJSON<TokenEventData>(frame).text,
              }))
              break
            case "done": {
              const payload = parseJSON<DoneEventData>(frame)
              const { text, ...meta } = payload
              setLiveAnswer((prev) => ({ ...prev, text, meta, done: true }))
              onDone?.(payload, sources)
              break
            }
            case "error":
              setLiveAnswer((prev) => ({
                ...prev,
                error: parseJSON<ErrorEventData>(frame).message,
                done: true,
              }))
              break
          }
        }
      } catch (error) {
        if (error instanceof DOMException && error.name === "AbortError") return
        setLiveAnswer((prev) => ({
          ...prev,
          error:
            error instanceof ApiError
              ? error.message
              : "Couldn't reach StudyBot. Check your connection.",
          done: true,
        }))
      } finally {
        setSending(false)
      }
    },
    [],
  )

  const stop = useCallback(() => controllerRef.current?.abort(), [])

  const clear = useCallback(() => {
    setLiveUser(null)
    setLiveAnswer(EMPTY_ANSWER)
  }, [])

  return { liveUser, liveAnswer, sending, send, stop, clear }
}
