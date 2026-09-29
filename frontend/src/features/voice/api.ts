import { api, ApiError } from "@/lib/api"

export interface VoiceStatus {
  available: boolean
  ready: boolean
  model: string | null
  error: string | null
}

export interface TranscribeResult {
  text: string
  audio_seconds: number
  seconds: number
}

function extensionFor(mimeType: string): string {
  if (mimeType.includes("mp4")) return "m4a"
  if (mimeType.includes("ogg")) return "ogg"
  return "webm"
}

export const voiceApi = {
  status: () => api.get<VoiceStatus>("/api/voice/status"),
  transcribe: async (blob: Blob): Promise<TranscribeResult> => {
    const form = new FormData()
    form.append("audio", blob, `speech.${extensionFor(blob.type)}`)
    const response = await fetch("/api/voice/transcribe", {
      method: "POST",
      credentials: "same-origin",
      body: form,
    })
    if (!response.ok) {
      const body = await response.json().catch(() => null)
      const detail =
        body && typeof body.detail === "string"
          ? body.detail
          : `Transcription failed (${response.status}).`
      throw new ApiError(response.status, detail)
    }
    return response.json()
  },
}
