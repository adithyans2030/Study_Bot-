import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { libraryApi } from "./api"

export const collectionsKey = ["collections"] as const
export const documentsKey = (collection?: string) => ["documents", collection ?? "*"] as const

export function useCollections() {
  return useQuery({ queryKey: collectionsKey, queryFn: libraryApi.collections.list })
}

export function useDocuments(collection?: string) {
  return useQuery({
    queryKey: documentsKey(collection),
    queryFn: () => libraryApi.documents.list(collection),
  })
}

export function useCreateCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: libraryApi.collections.create,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: collectionsKey }),
  })
}

export function useDeleteCollection() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: libraryApi.collections.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionsKey })
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
  })
}

export function useDeleteDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: libraryApi.documents.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: collectionsKey })
      queryClient.invalidateQueries({ queryKey: ["documents"] })
    },
  })
}

export function useReindexDocument() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: libraryApi.documents.reindex,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["documents"] }),
  })
}

export function useAddYoutube() {
  return useMutation({
    mutationFn: ({ url, collection }: { url: string; collection?: string }) =>
      libraryApi.documents.addYoutube(url, collection),
  })
}
