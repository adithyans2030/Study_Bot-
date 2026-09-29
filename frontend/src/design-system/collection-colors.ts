/** The fixed, accessible palette a collection's color is drawn from. There's no picker: the real
 * `collections` table has no color column, so a chosen color would only live in this browser and
 * silently vanish on another device — worse than not offering the choice at all. Instead each
 * collection gets a color deterministically from its id (`colorForCollection`), which is stable,
 * consistent everywhere the collection is shown, and needs nothing from the server. Values live
 * in tokens.css as --collection-*. */
export const COLLECTION_COLORS = [
  "indigo",
  "violet",
  "pink",
  "rose",
  "orange",
  "amber",
  "emerald",
  "teal",
  "sky",
  "slate",
] as const

export type CollectionColor = (typeof COLLECTION_COLORS)[number]

export const DEFAULT_COLLECTION_COLOR: CollectionColor = "indigo"

export function collectionColorVar(color: CollectionColor): string {
  return `var(--collection-${color})`
}

export function isCollectionColor(value: string): value is CollectionColor {
  return (COLLECTION_COLORS as readonly string[]).includes(value)
}

export function colorForCollection(id: number): CollectionColor {
  return COLLECTION_COLORS[id % COLLECTION_COLORS.length]
}
