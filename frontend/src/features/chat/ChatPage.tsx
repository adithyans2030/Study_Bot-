import { AlertCircle, Menu, RotateCcw } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { useQueryClient } from "@tanstack/react-query"
import { Navigate, useNavigate, useParams, useSearchParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Sheet, SheetContent, SheetTitle } from "@/components/ui/sheet"
import { ThemeToggle } from "@/design-system/ThemeToggle"
import { conversationKey, conversationsKey, useConversation } from "@/features/conversations/hooks"
import { AnswerBubble, type AnswerBubbleData } from "./AnswerBubble"
import { CollectionFilter } from "./CollectionFilter"
import { Composer } from "./Composer"
import { ConversationSidebar } from "./ConversationSidebar"
import { SourcePanel } from "./SourcePanel"
import type { Source } from "./types"
import { useChatStream } from "./useChatStream"
import { VoiceButton } from "@/features/voice/VoiceButton"
import { ReadAloudToggle } from "@/features/voice/ReadAloudToggle"
import { useReadAloud } from "@/features/voice/useReadAloud"

export function ChatPage() {
  const params = useParams<{ conversationId?: string }>()
  const conversationId = params.conversationId ? Number(params.conversationId) : null
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const [collectionFilter, setCollectionFilter] = useState<string | null>(
    searchParams.get("collection"),
  )
  const [question, setQuestion] = useState("")
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [openSources, setOpenSources] = useState<Source[] | null>(null)
  const [activeSourceIndex, setActiveSourceIndex] = useState<number | null>(null)

  const conversation = useConversation(conversationId)
  const stream = useChatStream()
  const readAloud = useReadAloud()
  const pendingConversationId = useRef<number | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const stickToBottom = useRef(true)

  useEffect(() => {
    readAloud.speakStreaming(stream.liveAnswer.text, stream.liveAnswer.done)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only the text/done fields should retrigger this
  }, [stream.liveAnswer.text, stream.liveAnswer.done])

  // React Router reuses this same component instance across /app/chat/:id navigations (it's one
  // route, just a different param) — without this, "New chat" or switching conversations in the
  // sidebar would leave the previous conversation's still-live question/answer showing instead of
  // the new (or empty) one. Skipped when *this* send() is the one that caused the URL to change
  // (a brand-new chat's id becoming known mid-stream, via pendingConversationId) — otherwise it
  // would wipe out the answer that's still streaming the moment its id arrives.
  useEffect(() => {
    if (conversationId === pendingConversationId.current) return
    stream.clear()
    setOpenSources(null)
    setActiveSourceIndex(null)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- only conversationId should trigger this reset
  }, [conversationId])

  useEffect(() => {
    const el = scrollRef.current
    if (el && stickToBottom.current) el.scrollTop = el.scrollHeight
  }, [stream.liveAnswer.text, stream.liveUser, conversation.data?.messages?.length])

  if (conversationId !== null && conversation.isError) {
    return <Navigate to="/app/chat" replace />
  }

  const send = async (text: string) => {
    setQuestion("")
    pendingConversationId.current = conversationId
    await stream.send(
      text,
      { collections: collectionFilter ? [collectionFilter] : undefined, conversationId },
      (data) => {
        pendingConversationId.current = data.id
        if (conversationId === null) navigate(`/app/chat/${data.id}`, { replace: true })
      },
      async () => {
        const id = pendingConversationId.current
        await Promise.all([
          id !== null
            ? queryClient.invalidateQueries({ queryKey: conversationKey(id) })
            : Promise.resolve(),
          queryClient.invalidateQueries({ queryKey: conversationsKey }),
        ])
        stream.clear()
      },
    )
  }

  const retry = () => {
    const failed = stream.liveUser
    stream.clear()
    if (failed) send(failed)
  }

  const savedBubbles: Array<{
    role: "user" | "assistant"
    content: string
    data?: AnswerBubbleData
    sources: Source[]
  }> = (conversation.data?.messages ?? []).map((m) => ({
    role: m.role,
    content: m.content,
    sources: m.sources,
    data:
      m.role === "assistant"
        ? {
            content: m.content,
            sources: m.sources,
            meta: m.meta,
            streaming: false,
            searchQuery: m.meta.search_query,
          }
        : undefined,
  }))

  const showLive = stream.liveUser !== null
  const title = conversation.data?.title ?? (showLive ? stream.liveUser! : "New chat")

  const openCitation = (sources: Source[]) => (n: number) => {
    const index = sources.findIndex((s) => s.n === n)
    setOpenSources(sources)
    setActiveSourceIndex(index === -1 ? null : index)
  }

  const sidebar = <ConversationSidebar activeId={conversationId} />

  return (
    <div className="flex h-svh">
      <div className="border-border hidden w-72 shrink-0 border-r lg:block">{sidebar}</div>
      <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
        <SheetContent side="left" className="w-72 p-0">
          <SheetTitle className="sr-only">Chat history</SheetTitle>
          {sidebar}
        </SheetContent>
      </Sheet>

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="border-border flex h-14 items-center gap-2 border-b px-3">
          <Button
            variant="ghost"
            size="icon"
            className="lg:hidden"
            onClick={() => setSidebarOpen(true)}
            aria-label="Chat history"
          >
            <Menu />
          </Button>
          <h1 id="chat-title" className="min-w-0 flex-1 truncate font-medium">
            {title}
          </h1>
          <CollectionFilter value={collectionFilter} onChange={setCollectionFilter} />
          <ThemeToggle />
        </header>

        <div
          ref={scrollRef}
          onScroll={(e) => {
            const el = e.currentTarget
            stickToBottom.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
          }}
          className="flex-1 overflow-y-auto"
        >
          {conversationId !== null && conversation.isPending ? (
            <p className="text-muted-foreground p-6 text-sm">Loading…</p>
          ) : conversationId === null && !showLive ? (
            <EmptyState collection={collectionFilter} onAsk={setQuestion} />
          ) : (
            <div className="mx-auto max-w-3xl space-y-6 p-4 sm:p-6">
              {savedBubbles.map((bubble, i) =>
                bubble.role === "user" ? (
                  <UserBubble key={i} text={bubble.content} />
                ) : (
                  <AnswerBubble
                    key={i}
                    data={bubble.data!}
                    onCiteClick={openCitation(bubble.sources)}
                  />
                ),
              )}

              {showLive && (
                <>
                  <UserBubble text={stream.liveUser!} />
                  <AnswerBubble
                    data={{
                      content: stream.liveAnswer.text,
                      sources: stream.liveAnswer.sources,
                      meta: stream.liveAnswer.meta,
                      searchQuery: stream.liveAnswer.searchQuery,
                      streaming: !stream.liveAnswer.done,
                    }}
                    onCiteClick={openCitation(stream.liveAnswer.sources)}
                  />
                  {stream.liveAnswer.error && (
                    <div className="border-destructive/30 bg-destructive/5 flex items-center gap-2 rounded-md border p-3 text-sm">
                      <AlertCircle className="text-destructive size-4 shrink-0" />
                      <p className="flex-1">{stream.liveAnswer.error}</p>
                      <Button variant="outline" size="sm" onClick={retry}>
                        <RotateCcw /> Retry
                      </Button>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </div>

        <div className="mx-auto w-full max-w-3xl">
          <div className="flex items-center gap-3 px-4 pt-2 sm:px-6">
            <ReadAloudToggle
              enabled={readAloud.enabled}
              onEnabledChange={readAloud.setEnabled}
              voices={readAloud.voices}
              voiceName={readAloud.voiceName}
              onVoiceNameChange={readAloud.setVoiceName}
            />
          </div>
          <div className="flex items-end gap-2 px-4 sm:px-6">
            <div className="flex-1">
              <Composer
                value={question}
                onChange={setQuestion}
                onSend={() => send(question)}
                onStop={stream.stop}
                sending={stream.sending}
                placeholder={
                  collectionFilter
                    ? `Ask a question about ${collectionFilter}…`
                    : "Ask a question about your notes…"
                }
              />
            </div>
            <div className="pb-3">
              <VoiceButton onTranscribed={(text) => send(text)} />
            </div>
          </div>
        </div>
      </main>

      <SourcePanel
        sources={openSources ?? []}
        activeIndex={activeSourceIndex}
        onActiveIndexChange={setActiveSourceIndex}
        onClose={() => setActiveSourceIndex(null)}
      />
    </div>
  )
}

function UserBubble({ text }: { text: string }) {
  return (
    <div className="flex justify-end">
      <div className="bg-secondary max-w-[85%] rounded-2xl px-4 py-2 text-sm">{text}</div>
    </div>
  )
}

function EmptyState({
  collection,
  onAsk,
}: {
  collection: string | null
  onAsk: (q: string) => void
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
      <h2 className="text-lg font-medium">
        Ask anything{collection ? ` from ${collection}` : " from your notes"}
      </h2>
      <p className="text-muted-foreground max-w-sm text-sm">
        Type a question below, or press the microphone to ask out loud.
      </p>
      <div className="mt-2 hidden gap-2 sm:flex">
        {["Summarize the key ideas", "What are the main differences discussed?"].map(
          (suggestion) => (
            <Button key={suggestion} variant="outline" size="sm" onClick={() => onAsk(suggestion)}>
              {suggestion}
            </Button>
          ),
        )}
      </div>
    </div>
  )
}
