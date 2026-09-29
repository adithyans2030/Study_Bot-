import { Loader2, Mic, Square } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"
import { isVoiceSupported, useVoiceStatus } from "./hooks"
import { useVoiceRecorder } from "./useVoiceRecorder"

export function VoiceButton({ onTranscribed }: { onTranscribed: (text: string) => void }) {
  const status = useVoiceStatus()
  const recorder = useVoiceRecorder(onTranscribed)

  if (!isVoiceSupported()) return null

  const usable = status.data?.available !== false
  const disabled = !usable || recorder.state === "working"
  const label =
    recorder.state === "listening"
      ? "Stop listening"
      : !usable
        ? `Voice input is unavailable: ${status.data?.error ?? "not installed"}`
        : status.data?.ready === false
          ? "Ask by voice (the speech model is still loading)"
          : "Ask by voice"

  return (
    <div className="flex flex-col items-center gap-1">
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            type="button"
            size="icon"
            variant={recorder.state === "listening" ? "default" : "outline"}
            className={recorder.state === "listening" ? "animate-pulse" : ""}
            disabled={disabled}
            onClick={recorder.toggle}
            aria-label={label}
          >
            {recorder.state === "working" ? (
              <Loader2 className="animate-spin" />
            ) : recorder.state === "listening" ? (
              <Square className="fill-current" />
            ) : (
              <Mic />
            )}
          </Button>
        </TooltipTrigger>
        <TooltipContent>{label}</TooltipContent>
      </Tooltip>
      {recorder.note && (
        <p className="text-muted-foreground max-w-32 text-center text-[11px]" role="status">
          {recorder.note}
        </p>
      )}
    </div>
  )
}
