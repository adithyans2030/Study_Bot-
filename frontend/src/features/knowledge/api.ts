import { useQuery } from "@tanstack/react-query"

const BASE = "/api/knowledge"

export interface KnowledgeNode {
  id: number
  type: string
  title: string
  description: string
  body: string
  tags: string[]
  trust: string
  source_document: string
  document_id: number
  collection_id: number
}

export interface KnowledgeStats {
  total_nodes: number
  documents_covered: number
  nodes_by_type: Record<string, number>
}

export interface SearchResult extends KnowledgeNode {
  score: number
}

export async function fetchNodes(params: {
  collection_id?: number
  node_type?: string
  limit?: number
}): Promise<KnowledgeNode[]> {
  const p = new URLSearchParams()
  if (params.collection_id != null) p.set("collection_id", String(params.collection_id))
  if (params.node_type) p.set("node_type", params.node_type)
  if (params.limit) p.set("limit", String(params.limit))
  const res = await fetch(`${BASE}?${p}`)
  if (!res.ok) throw new Error("Failed to fetch knowledge nodes")
  return res.json()
}

export async function searchNodes(q: string, collection_id?: number): Promise<SearchResult[]> {
  const p = new URLSearchParams({ q })
  if (collection_id != null) p.set("collection_id", String(collection_id))
  const res = await fetch(`${BASE}/search?${p}`)
  if (!res.ok) throw new Error("Search failed")
  return res.json()
}

export async function fetchStats(collection_id?: number): Promise<KnowledgeStats> {
  const p = new URLSearchParams()
  if (collection_id != null) p.set("collection_id", String(collection_id))
  const res = await fetch(`${BASE}/stats?${p}`)
  if (!res.ok) throw new Error("Failed to fetch stats")
  return res.json()
}

export function exportZipUrl(collection_id?: number) {
  const p = new URLSearchParams()
  if (collection_id != null) p.set("collection_id", String(collection_id))
  return `${BASE}/export/zip?${p}`
}

export function useKnowledgeNodes(collectionId?: number, nodeType?: string) {
  return useQuery({
    queryKey: ["knowledge", "nodes", collectionId, nodeType],
    queryFn: () => fetchNodes({ collection_id: collectionId, node_type: nodeType, limit: 300 }),
    staleTime: 60_000,
  })
}

export function useKnowledgeSearch(q: string, collectionId?: number) {
  return useQuery({
    queryKey: ["knowledge", "search", q, collectionId],
    queryFn: () => searchNodes(q, collectionId),
    enabled: q.trim().length > 2,
    staleTime: 30_000,
  })
}

export function useKnowledgeStats(collectionId?: number) {
  return useQuery({
    queryKey: ["knowledge", "stats", collectionId],
    queryFn: () => fetchStats(collectionId),
    staleTime: 60_000,
  })
}
