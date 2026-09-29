export interface Source {
  n: number
  title: string
  type: "pdf" | "pptx" | "docx" | "youtube"
  location: string // "p.3", "slide 4", "12:34", or "" if not applicable
  url: string | null // a YouTube deep link, only when type === "youtube"
  header: string // "Doc title › Heading"
  snippet: string
}

export interface AnswerMeta {
  cited: number[]
  invalid_citations: number
  refused: boolean
  gated: boolean
  empty: boolean
  seconds?: number
  search_query?: string
}

/** A message as StudyBot saves and later replays it (GET /api/conversations/{id}). */
export interface SavedMessage {
  id: number
  role: "user" | "assistant"
  content: string
  sources: Source[]
  meta: Partial<AnswerMeta>
  created_at: number
}

export interface ConversationSummary {
  id: number
  title: string
  updated_at: number
}

export interface ConversationDetail extends ConversationSummary {
  created_at: number
  messages: SavedMessage[]
}

// ---- POST /api/chat SSE event payloads, in the order they can arrive -------------------------

export interface ConversationEventData {
  id: number
  title: string
}
export interface QueryEventData {
  text: string
}
export type SourcesEventData = Source[]
export interface TokenEventData {
  text: string
}
export interface DoneEventData {
  text: string
  cited: number[]
  invalid_citations: number
  refused: boolean
  gated: boolean
  empty: boolean
  seconds: number
  first_token_seconds: number
}
export interface ErrorEventData {
  message: string
}
