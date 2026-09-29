import { GraduationCap, MessageSquarePlus, Trash2 } from "lucide-react"
import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ConfirmDialog } from "@/design-system/ConfirmDialog"
import { parseUnixSeconds } from "@/lib/format"
import { useConversations, useDeleteConversation } from "@/features/conversations/hooks"
import type { ConversationSummary } from "./types"

const GROUPS: Array<{ label: string; test: (days: number) => boolean }> = [
  { label: "Today", test: (d) => d < 1 },
  { label: "Yesterday", test: (d) => d < 2 },
  { label: "Previous 7 days", test: (d) => d < 7 },
  { label: "Older", test: () => true },
]

function groupByRecency(conversations: ConversationSummary[]) {
  const now = Date.now()
  const groups = new Map<string, ConversationSummary[]>()
  for (const conversation of conversations) {
    const days = (now - parseUnixSeconds(conversation.updated_at).getTime()) / 86_400_000
    const group = GROUPS.find((g) => g.test(days))!.label
    if (!groups.has(group)) groups.set(group, [])
    groups.get(group)!.push(conversation)
  }
  return groups
}

export function ConversationSidebar({ activeId }: { activeId: number | null }) {
  const conversations = useConversations()
  const deleteConversation = useDeleteConversation()
  const navigate = useNavigate()
  const [deleting, setDeleting] = useState<ConversationSummary | null>(null)

  const groups = conversations.data ? groupByRecency(conversations.data) : null

  return (
    <nav className="flex h-full flex-col gap-3 p-3" aria-label="Chat history">
      {/* The chat page has its own full-screen layout, separate from AppShell — this is the only
          way back to the library (and from there, the account menu / sign out) once you're here. */}
      <Link to="/app" className="flex items-center gap-2 px-1 py-1 text-sm font-semibold">
        <GraduationCap className="size-5" />
        StudyBot
      </Link>
      <Button variant="outline" className="justify-start" asChild>
        <Link to="/app/chat">
          <MessageSquarePlus /> New chat
        </Link>
      </Button>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {conversations.isPending ? (
          <div className="space-y-2 p-1">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-8 rounded-md" />
            ))}
          </div>
        ) : groups && groups.size > 0 ? (
          [...groups.entries()].map(([label, items]) => (
            <div key={label} className="mb-3">
              <p className="text-muted-foreground px-2 py-1 text-xs font-medium">{label}</p>
              <ul>
                {items.map((conversation) => (
                  <li key={conversation.id} className="group relative">
                    <Link
                      to={`/app/chat/${conversation.id}`}
                      className={`hover:bg-muted block truncate rounded-md px-2 py-1.5 pr-8 text-sm ${
                        conversation.id === activeId ? "bg-muted font-medium" : ""
                      }`}
                    >
                      {conversation.title}
                    </Link>
                    <button
                      type="button"
                      aria-label={`Delete "${conversation.title}"`}
                      onClick={() => setDeleting(conversation)}
                      className="text-muted-foreground hover:text-destructive absolute top-1/2 right-1 -translate-y-1/2 rounded p-1 opacity-0 group-hover:opacity-100 focus-visible:opacity-100"
                    >
                      <Trash2 className="size-3.5" />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ))
        ) : (
          <p className="text-muted-foreground p-2 text-sm">No chats yet.</p>
        )}
      </div>

      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.title}"?`}
        description="This permanently deletes the conversation. This can't be undone."
        onConfirm={() => {
          if (!deleting) return
          const wasActive = deleting.id === activeId
          deleteConversation.mutate(deleting.id)
          setDeleting(null)
          if (wasActive) navigate("/app/chat")
        }}
      />
    </nav>
  )
}
