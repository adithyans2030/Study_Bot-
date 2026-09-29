import { Laptop, Moon, Sun } from "lucide-react"
import { useTheme } from "next-themes"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

const OPTIONS = [
  { value: "light", label: "Light", icon: Sun },
  { value: "dark", label: "Dark", icon: Moon },
  { value: "system", label: "Match system", icon: Laptop },
] as const

/** Cycles light -> dark -> system. A student who never touches it gets the OS setting; one who
 * does gets their choice remembered (next-themes persists it to localStorage). */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme()
  const current = OPTIONS.find((o) => o.value === theme) ?? OPTIONS[2]
  const next = OPTIONS[(OPTIONS.indexOf(current) + 1) % OPTIONS.length]
  const Icon = current.icon

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          aria-label={`Appearance: ${current.label}. Switch to ${next.label}.`}
          onClick={() => setTheme(next.value)}
        >
          <Icon />
        </Button>
      </TooltipTrigger>
      <TooltipContent>{`Appearance: ${current.label}`}</TooltipContent>
    </Tooltip>
  )
}
