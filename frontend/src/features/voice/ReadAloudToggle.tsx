import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"

function shortVoiceName(name: string): string {
  return name.replace(/^Microsoft /, "").replace(/ (Desktop )?- English.*$/, "")
}

export function ReadAloudToggle({
  enabled,
  onEnabledChange,
  voices,
  voiceName,
  onVoiceNameChange,
}: {
  enabled: boolean
  onEnabledChange: (enabled: boolean) => void
  voices: SpeechSynthesisVoice[]
  voiceName: string
  onVoiceNameChange: (name: string) => void
}) {
  if (typeof window === "undefined" || !("speechSynthesis" in window)) return null

  const selected =
    voices.find((v) => v.name === voiceName) ?? voices.find((v) => v.localService) ?? voices[0]

  return (
    <div className="flex flex-wrap items-center gap-3 text-sm">
      <label className="flex items-center gap-2">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(e) => onEnabledChange(e.target.checked)}
          className="accent-primary size-4"
        />
        Read answers aloud
      </label>
      {voices.length > 0 && (
        <Select value={selected?.name} onValueChange={onVoiceNameChange} disabled={!enabled}>
          <SelectTrigger size="sm" aria-label="Voice for reading answers" className="w-auto">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {voices.map((v) => (
              <SelectItem key={v.name} value={v.name}>
                {shortVoiceName(v.name)}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      )}
    </div>
  )
}
