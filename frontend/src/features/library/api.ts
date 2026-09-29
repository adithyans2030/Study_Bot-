import { api, ApiError } from "@/lib/api"
import type { Job } from "./types"
import type { Collection, LibraryDocument } from "./types"

export const libraryApi = {
  collections: {
    list: () => api.get<Collection[]>("/api/collections"),
    create: (name: string) => api.post<Collection>("/api/collections", { name }),
    remove: (id: number) => api.delete<undefined>(`/api/collections/${id}`),
  },
  documents: {
    list: (collection?: string) =>
      api.get<LibraryDocument[]>(
        `/api/documents${collection ? `?collection=${encodeURIComponent(collection)}` : ""}`,
      ),
    remove: (id: number) => api.delete<undefined>(`/api/documents/${id}`),
    reindex: (id: number) => api.post<Job>(`/api/documents/${id}/reindex`),
    addYoutube: (url: string, collection?: string) =>
      api.post<Job>("/api/documents/youtube", { url, collection: collection ?? null }),
  },
}

/** Uses XMLHttpRequest, not fetch, only because fetch still can't report request upload progress
 * in every browser this needs to run in — `onProgress` is what drives each file's progress bar. */
export function uploadDocument(
  file: File,
  collection: string,
  onProgress: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<Job> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open("POST", "/api/documents")
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total)
    }
    xhr.onload = () => {
      let body: unknown = null
      try {
        body = JSON.parse(xhr.responseText)
      } catch {
        // handled by the status check below
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        onProgress(1)
        resolve(body as Job)
      } else {
        const detail =
          typeof body === "object" && body && "detail" in body
            ? (body as { detail: unknown }).detail
            : null
        reject(
          new ApiError(
            xhr.status,
            typeof detail === "string" ? detail : `Upload failed (${xhr.status}).`,
          ),
        )
      }
    }
    xhr.onerror = () => reject(new ApiError(0, "Upload failed. Check your connection to StudyBot."))
    xhr.onabort = () => reject(new DOMException("Upload cancelled", "AbortError"))
    if (signal) {
      if (signal.aborted) {
        xhr.abort()
        return
      }
      signal.addEventListener("abort", () => xhr.abort())
    }

    const body = new FormData()
    body.append("file", file)
    body.append("collection", collection)
    xhr.send(body)
  })
}
