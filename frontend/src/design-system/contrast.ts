/** WCAG 2.x contrast ratio between two sRGB colors, per the relative-luminance formula
 * (https://www.w3.org/TR/WCAG22/#dfn-contrast-ratio). Returns a value from 1 (no contrast) to
 * 21 (black on white). Used by tokens.contrast.test.ts to keep every design-token text/background
 * pairing honest, and safe to reuse anywhere a runtime contrast check is useful (e.g. validating a
 * collection's chosen accent color against its foreground before saving it). */

function relativeLuminance(hex: string): number {
  const channel = (value: number) => {
    const srgb = value / 255
    return srgb <= 0.03928 ? srgb / 12.92 : ((srgb + 0.055) / 1.055) ** 2.4
  }
  const { r, g, b } = hexToRgb(hex)
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)
}

function hexToRgb(hex: string): { r: number; g: number; b: number } {
  const normalized = hex.replace("#", "")
  const full =
    normalized.length === 3
      ? normalized
          .split("")
          .map((c) => c + c)
          .join("")
      : normalized
  const int = Number.parseInt(full, 16)
  return { r: (int >> 16) & 255, g: (int >> 8) & 255, b: int & 255 }
}

export function contrastRatio(hexA: string, hexB: string): number {
  const lumA = relativeLuminance(hexA)
  const lumB = relativeLuminance(hexB)
  const lighter = Math.max(lumA, lumB)
  const darker = Math.min(lumA, lumB)
  return (lighter + 0.05) / (darker + 0.05)
}

/** WCAG 2.2 AA thresholds: 4.5:1 for normal text, 3:1 for large text (≥24px, or ≥19px bold) and
 * for meaningful UI outlines/graphics. */
export const AA_NORMAL_TEXT = 4.5
export const AA_LARGE_TEXT_OR_UI = 3
