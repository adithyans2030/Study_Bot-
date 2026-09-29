import { api } from "@/lib/api"
import type { ConversationDetail, ConversationSummary } from "@/features/chat/types"

export const conversationsApi = {
  list: () => api.get<ConversationSummary[]>("/api/conversations"),
  get: (id: number) => api.get<ConversationDetail>(`/api/conversations/${id}`),
  remove: (id: number) => api.delete<undefined>(`/api/conversations/${id}`),
}
