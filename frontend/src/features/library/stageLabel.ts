import type { JobStage } from "./types"

/** Plain-language progress, matching the design principle "always tell the student what's
 * happening" rather than a bare "processing" spinner. */
export function stageLabel(stage: JobStage): string {
  switch (stage) {
    case "starting":
      return "Starting…"
    case "reading":
      return "Reading your notes…"
    case "chunking":
      return "Organizing the content…"
    case "embedding":
      return "Understanding the content…"
    case "indexing":
      return "Almost ready…"
    case "done":
      return "Ready"
    case "failed":
      return "Failed"
    default:
      return "Working…"
  }
}
