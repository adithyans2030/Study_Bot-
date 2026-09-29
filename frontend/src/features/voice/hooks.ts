import { useQuery } from "@tanstack/react-query"
import { voiceApi } from "./api"

// typeof-checked rather than `!!window.MediaRecorder`: TS's DOM lib declares that constructor as
// always present, so it considers a truthiness check on the reference itself always-true — this
// is the pattern for feature-detecting a global TS assumes exists, for a browser that actually might not.
const supported = !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined"

export function useVoiceStatus() {
  return useQuery({
    queryKey: ["voice", "status"],
    queryFn: voiceApi.status,
    enabled: supported,
    staleTime: 30_000,
  })
}

export function isVoiceSupported() {
  return supported
}
