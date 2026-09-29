import { useEffect } from "react"
import { useJobEvents } from "./useJobEvents"
import type { Job } from "@/features/library/types"

/** Renders nothing — just runs `useJobEvents` for one job and reports every update up. One of
 * these per in-progress upload, so each gets its own SSE subscription (a plain hook can't be
 * called a dynamic number of times, but a dynamic number of tiny components each calling it
 * once is exactly the same thing and is the idiomatic way to do this in React). */
export function JobWatcher({ jobId, onUpdate }: { jobId: string; onUpdate: (job: Job) => void }) {
  const job = useJobEvents(jobId)
  useEffect(() => {
    if (job) onUpdate(job)
    // eslint-disable-next-line react-hooks/exhaustive-deps -- onUpdate is a stable dispatch-like callback from the caller
  }, [job])
  return null
}
