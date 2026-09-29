import { describe, expect, it } from "vitest"
import { AA_NORMAL_TEXT, contrastRatio } from "./contrast"
import { dark, light, type Palette } from "./palette"

// Every token pair that actually carries text somewhere in the design system (§4.1: "every
// text/background pair must meet 4.5:1"). `muted-foreground` is checked against both
// `background` and `card` since it's used as secondary text in both contexts.
const pairs: Array<[fg: keyof Palette, bg: keyof Palette]> = [
  ["foreground", "background"],
  ["foreground", "card"],
  ["mutedForeground", "background"],
  ["mutedForeground", "card"],
  ["cardForeground", "card"],
  ["popoverForeground", "popover"],
  ["primaryForeground", "primary"],
  ["secondaryForeground", "secondary"],
  ["accentForeground", "accent"],
  ["destructiveForeground", "destructive"],
  ["evidenceForeground", "evidence"],
]

describe.each([
  ["light", light],
  ["dark", dark],
] as const)("%s theme meets WCAG AA (4.5:1) for text", (_name, palette) => {
  it.each(pairs)("%s on %s", (fg, bg) => {
    const ratio = contrastRatio(palette[fg], palette[bg])
    expect(ratio).toBeGreaterThanOrEqual(AA_NORMAL_TEXT)
  })
})
