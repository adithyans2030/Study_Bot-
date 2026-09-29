/** The same color values as `src/styles/tokens.css`, duplicated here so `contrastRatio()` (a
 * plain TS function) can check them in a test without parsing CSS. There's no build step that
 * generates one file from the other — if you change a color in tokens.css, update it here too.
 * `tokens.contrast.test.ts` covers the pairs that actually carry text. */

export const light = {
  background: "#f8f9fb",
  foreground: "#14171f",
  card: "#ffffff",
  cardForeground: "#14171f",
  popover: "#ffffff",
  popoverForeground: "#14171f",
  primary: "#4f46e5",
  primaryForeground: "#ffffff",
  secondary: "#f1f3f7",
  secondaryForeground: "#14171f",
  muted: "#f1f3f7",
  mutedForeground: "#5b6272",
  accent: "#e7e9f0",
  accentForeground: "#14171f",
  destructive: "#b91c1c",
  destructiveForeground: "#ffffff",
  evidence: "#b45309",
  evidenceForeground: "#ffffff",
} as const

export const dark = {
  background: "#0f1115",
  foreground: "#eceef2",
  card: "#171a21",
  cardForeground: "#eceef2",
  popover: "#171a21",
  popoverForeground: "#eceef2",
  primary: "#818cf8",
  primaryForeground: "#0f1115",
  secondary: "#1e222b",
  secondaryForeground: "#eceef2",
  muted: "#1e222b",
  mutedForeground: "#9aa1b0",
  accent: "#262b36",
  accentForeground: "#eceef2",
  destructive: "#f87171",
  destructiveForeground: "#0f1115",
  evidence: "#fbbf24",
  evidenceForeground: "#14171f",
} as const

export type Palette = typeof light
