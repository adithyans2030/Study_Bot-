import { useCallback, useEffect, useRef, useState } from "react"
import { speakable, splitSentences } from "@/lib/rich"

const PREFS_KEY = "studybot.readAloud"
const supported = typeof window !== "undefined" && "speechSynthesis" in window

function loadPrefs(): { enabled: boolean; voiceName: string } {
  try {
    const raw = localStorage.getItem(PREFS_KEY)
    if (raw) return { enabled: false, voiceName: "", ...JSON.parse(raw) }
  } catch {
    // Private browsing or a disabled localStorage — fall back to defaults below.
  }
  return { enabled: false, voiceName: "" }
}

function savePrefs(prefs: { enabled: boolean; voiceName: string }) {
  try {
    localStorage.setItem(PREFS_KEY, JSON.stringify(prefs))
  } catch {
    // Nothing to recover; it's a convenience, not a requirement.
  }
}

function englishVoices(): SpeechSynthesisVoice[] {
  if (!supported) return []
  return window.speechSynthesis.getVoices().filter((v) => v.lang.toLowerCase().startsWith("en"))
}

/** Speaks an answer sentence by sentence as it streams in — first audio well before the whole
 * answer has arrived — using the device's own voices (no server, no cost, works offline).
 * Ported from the plain-JS dashboard's `speaker` object onto React state. */
export function useReadAloud() {
  // Lazy initializers (not an effect + setState after mount): localStorage is available
  // synchronously in a browser SPA with no server-rendered pass to match, so there's no reason to
  // pay for an extra render just to move the read from render-time to effect-time.
  const [enabled, setEnabledState] = useState(() => loadPrefs().enabled)
  const [voiceName, setVoiceNameState] = useState(() => loadPrefs().voiceName)
  const [voices, setVoices] = useState<SpeechSynthesisVoice[]>([])
  const processedUpTo = useRef(0)

  useEffect(() => {
    if (!supported) return
    const refresh = () => setVoices(englishVoices())
    refresh()
    window.speechSynthesis.addEventListener("voiceschanged", refresh)
    return () => window.speechSynthesis.removeEventListener("voiceschanged", refresh)
  }, [])

  const pickVoice = useCallback((): SpeechSynthesisVoice | null => {
    return (
      voices.find((v) => v.name === voiceName) ??
      voices.find((v) => v.localService) ??
      voices[0] ??
      null
    )
  }, [voices, voiceName])

  const stop = useCallback(() => {
    if (supported) window.speechSynthesis.cancel()
  }, [])

  const setEnabled = useCallback(
    (next: boolean) => {
      setEnabledState(next)
      savePrefs({ enabled: next, voiceName })
      if (!next) stop()
    },
    [voiceName, stop],
  )

  const setVoiceName = useCallback(
    (next: string) => {
      setVoiceNameState(next)
      savePrefs({ enabled, voiceName: next })
    },
    [enabled],
  )

  const say = useCallback(
    (text: string) => {
      const clean = speakable(text)
      if (!clean || !supported) return
      const utterance = new SpeechSynthesisUtterance(clean)
      const voice = pickVoice()
      if (voice) utterance.voice = voice
      window.speechSynthesis.speak(utterance)
    },
    [pickVoice],
  )

  /** Call on every render of a streaming answer with its cumulative text so far, and `true` for
   * `done` once (and only once) when it finishes — queues newly-completed sentences each time. */
  const speakStreaming = useCallback(
    (text: string, done: boolean) => {
      if (!enabled) {
        processedUpTo.current = 0
        return
      }
      if (text.length < processedUpTo.current) processedUpTo.current = 0 // a new answer started

      const remainder = text.slice(processedUpTo.current)
      const [finished, rest] = splitSentences(remainder)
      for (const sentence of finished) say(sentence)
      processedUpTo.current = text.length - rest.length

      if (done && rest) {
        say(rest)
        processedUpTo.current = text.length
      }
      if (done) processedUpTo.current = 0
    },
    [enabled, say],
  )

  return { supported, enabled, setEnabled, voices, voiceName, setVoiceName, speakStreaming, stop }
}
