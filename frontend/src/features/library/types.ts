export interface Collection {
  id: number
  name: string
  documents: number
  chunks: number
}

export type DocumentType = "pdf" | "pptx" | "docx" | "youtube"

export interface LibraryDocument {
  id: number
  title: string
  type: DocumentType
  collection: string
  collection_id: number
  chunks: number
  warnings: string[]
  url: string | null
  added: number
}

export type JobStatus = "pending" | "running" | "done" | "failed"
export type JobStage =
  "starting" | "reading" | "chunking" | "embedding" | "indexing" | "done" | "failed" | string

export interface Job {
  id: string
  kind: "file" | "youtube" | "reindex"
  collection: string
  title: string | null
  status: JobStatus
  stage: JobStage
  error: string | null
  document_id: number | null
  chunks: number | null
  warnings: string[]
  created_at: number
  updated_at: number
}
