import { useCallback, useRef, useState } from "react"
import { voiceApi } from "./api"

export type RecorderState = "idle" | "listening" | "working"

const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"]
const SILENCE_RMS = 0.02
const SILENCE_MS = 1500 // stop this long after speech, once some has been heard
const MAX_MS = 30_000 // hard cap regardless of speech
const NO_SPEECH_TIMEOUT_MS = 8_000 // give up if nothing at all was heard

function pickMimeType(): string {
  return MIME_TYPES.find((t) => MediaRecorder.isTypeSupported?.(t)) ?? ""
}

function micProblem(err: unknown): string {
  if (!window.isSecureContext) {
    return "The microphone only works on https:// pages or on this computer (localhost). Open StudyBot from this PC, or through its HTTPS address."
  }
  const name = err instanceof DOMException ? err.name : ""
  if (name === "NotAllowedError" || name === "SecurityError") {
    return "Microphone access was blocked. Allow it in the browser's address bar, then try again."
  }
  if (name === "NotFoundError") return "No microphone was found."
  return `Could not start the microphone: ${err instanceof Error ? err.message : "unknown error"}`
}

/** Records until you stop talking, the same way the original plain-JS dashboard did: an
 * AudioContext analyser watches the RMS volume and stops the recording 1.5s after speech last
 * crossed the threshold, so no second tap is needed. Ported 1:1 rather than redesigned — this
 * algorithm was already tuned against real speech in an earlier session. */
export function useVoiceRecorder(onTranscribed: (text: string) => void) {
  const [state, setState] = useState<RecorderState>("idle")
  const [note, setNote] = useState("")
  const recorderRef = useRef<MediaRecorder | null>(null)
  const stopRef = useRef<(() => void) | null>(null)

  const start = useCallback(async () => {
    setNote("")
    let stream: MediaStream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true },
      })
    } catch (err) {
      setNote(micProblem(err))
      return
    }

    const mimeType = pickMimeType()
    const recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined)
    const chunks: Blob[] = []
    recorder.ondataavailable = (e) => {
      if (e.data.size) chunks.push(e.data)
    }

    const AudioCtx =
      window.AudioContext ??
      (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext
    const context = new AudioCtx()
    const analyser = context.createAnalyser()
    analyser.fftSize = 1024
    context.createMediaStreamSource(stream).connect(analyser)
    const samples = new Uint8Array(analyser.fftSize)
    const began = Date.now()
    let heardSpeech = false
    let lastVoice = Date.now()

    const watcher = window.setInterval(() => {
      analyser.getByteTimeDomainData(samples)
      let sum = 0
      for (const v of samples) sum += ((v - 128) / 128) ** 2
      if (Math.sqrt(sum / samples.length) > SILENCE_RMS) {
        heardSpeech = true
        lastVoice = Date.now()
      }
      const elapsed = Date.now() - began
      if (
        (heardSpeech && Date.now() - lastVoice > SILENCE_MS) ||
        elapsed > MAX_MS ||
        (!heardSpeech && elapsed > NO_SPEECH_TIMEOUT_MS)
      ) {
        stopRef.current?.()
      }
    }, 100)

    recorderRef.current = recorder
    stopRef.current = () => {
      if (recorder.state !== "inactive") recorder.stop()
    }

    recorder.onstop = async () => {
      window.clearInterval(watcher)
      stream.getTracks().forEach((t) => t.stop())
      context.close().catch(() => {})
      recorderRef.current = null
      stopRef.current = null

      if (!heardSpeech) {
        setState("idle")
        setNote("I didn't hear anything. Try again, a little closer to the microphone.")
        return
      }
      setState("working")
      setNote("Transcribing…")
      try {
        const result = await voiceApi.transcribe(
          new Blob(chunks, { type: recorder.mimeType || mimeType || "audio/webm" }),
        )
        if (!result.text) {
          setNote("I didn't catch that. Please try again.")
        } else {
          setNote("")
          onTranscribed(result.text)
        }
      } catch (err) {
        setNote(err instanceof Error ? err.message : "Transcription failed.")
      } finally {
        setState("idle")
      }
    }

    recorder.start()
    setState("listening")
    setNote("Listening… speak your question, then pause.")
  }, [onTranscribed])

  const stop = useCallback(() => stopRef.current?.(), [])

  const toggle = useCallback(() => {
    if (recorderRef.current) stop()
    else start()
  }, [start, stop])

  return { state, note, toggle }
}
