import { useEffect, useRef, useState } from "react"
import { parseJSON, readSSE } from "@/lib/sse"
import type { Job } from "@/features/library/types"

/** Subscribes to `/api/jobs/{id}/events` and returns the job's live status as it moves through
 * reading -> chunking -> embedding -> indexing -> done|failed. Stops on its own once the job
 * reaches a terminal status (the server closes the stream at the same point). */
export function useJobEvents(jobId: string | null, onSettled?: (job: Job) => void) {
  const [job, setJob] = useState<Job | null>(null)
  const onSettledRef = useRef(onSettled)
  useEffect(() => {
    onSettledRef.current = onSettled
  }, [onSettled])

  useEffect(() => {
    if (!jobId) return
    const controller = new AbortController()

    async function run() {
      try {
        const response = await fetch(`/api/jobs/${jobId}/events`, { signal: controller.signal })
        if (!response.ok) return
        for await (const frame of readSSE(response)) {
          if (frame.event !== "job") continue
          const next = parseJSON<Job>(frame)
          setJob(next)
          if (next.status === "done" || next.status === "failed") onSettledRef.current?.(next)
        }
      } catch (error) {
        if ((error as Error).name !== "AbortError") throw error
      }
    }
    run()

    return () => controller.abort()
  }, [jobId])

  return job
}
