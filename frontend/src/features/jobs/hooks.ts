import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { Job } from "@/features/library/types"

const TERMINAL = new Set(["done", "failed"])

/** Which collections have material still indexing right now — covers a job started in another
 * tab or before a page reload, not just uploads made in this session (see useUploadQueue for
 * those, which get live SSE progress instead of this 5s poll). */
export function useActiveJobs() {
  return useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.get<Job[]>("/api/jobs"),
    refetchInterval: (query) => {
      const jobs = query.state.data ?? []
      return jobs.some((j) => !TERMINAL.has(j.status)) ? 3000 : false
    },
  })
}
