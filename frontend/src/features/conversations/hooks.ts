import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { conversationsApi } from "./api"

export const conversationsKey = ["conversations"] as const
export const conversationKey = (id: number) => ["conversations", id] as const

export function useConversations() {
  return useQuery({ queryKey: conversationsKey, queryFn: conversationsApi.list })
}

export function useConversation(id: number | null) {
  return useQuery({
    queryKey: id === null ? conversationsKey : conversationKey(id),
    queryFn: () => conversationsApi.get(id as number),
    enabled: id !== null,
  })
}

export function useDeleteConversation() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: conversationsApi.remove,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: conversationsKey }),
  })
}
