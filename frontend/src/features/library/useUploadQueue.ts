import { useQueryClient } from "@tanstack/react-query"
import { useCallback, useRef, useState } from "react"
import { ApiError } from "@/lib/api"
import { uploadDocument } from "./api"
import { collectionsKey, documentsKey } from "./hooks"
import type { Job } from "./types"

export type UploadPhase = "uploading" | "processing" | "done" | "failed"

export interface UploadItem {
  localId: string
  fileName: string
  collection: string
  phase: UploadPhase
  progress: number // 0-1 while uploading; ignored once processing (job.stage tells the story instead)
  job: Job | null
  error: string | null
}

let counter = 0

export function useUploadQueue() {
  const [items, setItems] = useState<UploadItem[]>([])
  const controllers = useRef(new Map<string, AbortController>())
  const queryClient = useQueryClient()

  const patch = useCallback((localId: string, partial: Partial<UploadItem>) => {
    setItems((prev) =>
      prev.map((item) => (item.localId === localId ? { ...item, ...partial } : item)),
    )
  }, [])

  const start = useCallback(
    (file: File, collection: string) => {
      const localId = `upload-${++counter}`
      const controller = new AbortController()
      controllers.current.set(localId, controller)
      setItems((prev) => [
        {
          localId,
          fileName: file.name,
          collection,
          phase: "uploading",
          progress: 0,
          job: null,
          error: null,
        },
        ...prev,
      ])

      uploadDocument(
        file,
        collection,
        (fraction) => patch(localId, { progress: fraction }),
        controller.signal,
      )
        .then((job) => {
          patch(localId, { phase: "processing", job })
        })
        .catch((error: unknown) => {
          if (error instanceof DOMException && error.name === "AbortError") {
            setItems((prev) => prev.filter((item) => item.localId !== localId))
            return
          }
          patch(localId, {
            phase: "failed",
            error: error instanceof ApiError ? error.message : "Upload failed.",
          })
        })
        .finally(() => controllers.current.delete(localId))

      return localId
    },
    [patch],
  )

  const cancel = useCallback((localId: string) => {
    controllers.current.get(localId)?.abort()
  }, [])

  const dismiss = useCallback((localId: string) => {
    setItems((prev) => prev.filter((item) => item.localId !== localId))
  }, [])

  const onJobUpdate = useCallback(
    (localId: string, job: Job) => {
      patch(localId, {
        job,
        phase: job.status === "done" ? "done" : job.status === "failed" ? "failed" : "processing",
      })
      if (job.status === "done" || job.status === "failed") {
        queryClient.invalidateQueries({ queryKey: collectionsKey })
        queryClient.invalidateQueries({ queryKey: documentsKey() })
      }
    },
    [patch, queryClient],
  )

  return { items, start, cancel, dismiss, onJobUpdate }
}
