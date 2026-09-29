import { FileText, MoreVertical, Trash2 } from "lucide-react"
import { Link } from "react-router-dom"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { colorForCollection, collectionColorVar } from "@/design-system/collection-colors"
import type { Collection } from "./types"

const SB_BORDER = "var(--border)"

export function CollectionCard({
  collection,
  processing,
  onDelete,
}: {
  collection: Collection
  processing: boolean
  onDelete: () => void
}) {
  const color = collectionColorVar(colorForCollection(collection.id))
  const initial = collection.name.charAt(0).toUpperCase()

  return (
    <Link
      to={`/app/c/${collection.id}`}
      style={{
        background: "var(--card)",
        border: `1px solid ${SB_BORDER}`,
        borderRadius: 16,
        padding: "24px 24px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 12,
        textDecoration: "none",
        position: "relative",
        transition: "box-shadow 0.2s, transform 0.2s",
        minHeight: 140,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.boxShadow = "0 6px 24px rgba(0,0,0,0.09)"
        e.currentTarget.style.transform = "translateY(-2px)"
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.boxShadow = "none"
        e.currentTarget.style.transform = "translateY(0)"
      }}
    >
      {/* Top row */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between" }}>
        {/* Letter avatar */}
        <div
          style={{
            width: 40,
            height: 40,
            borderRadius: 12,
            background: color,
            color: "#fff",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontFamily: "'Georgia',serif",
            fontWeight: 700,
            fontSize: 18,
            flexShrink: 0,
          }}
          aria-hidden
        >
          {initial}
        </div>

        {/* Actions */}
        <DropdownMenu>
          <DropdownMenuTrigger
            onClick={(e) => e.preventDefault()}
            style={{
              background: "transparent",
              border: "none",
              cursor: "pointer",
              padding: "4px 6px",
              borderRadius: 6,
              color: "var(--muted-foreground)",
              display: "flex",
              alignItems: "center",
            }}
            aria-label={`More actions for ${collection.name}`}
          >
            <MoreVertical style={{ width: 16, height: 16 }} />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" onClick={(e) => e.preventDefault()}>
            <DropdownMenuItem variant="destructive" onSelect={onDelete}>
              <Trash2 /> Delete collection
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>

      {/* Content */}
      <div>
        <h3
          style={{
            fontFamily: "'Georgia',serif",
            fontSize: 17,
            fontWeight: 700,
            color: "var(--foreground)",
            lineHeight: 1.3,
            marginBottom: 4,
            overflow: "hidden",
            textOverflow: "ellipsis",
            whiteSpace: "nowrap",
          }}
        >
          {collection.name}
        </h3>
        <p
          style={{
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            fontSize: 13,
            color: "var(--muted-foreground)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <FileText style={{ width: 13, height: 13 }} aria-hidden />
          {collection.documents} {collection.documents === 1 ? "note" : "notes"}
        </p>
      </div>

      {processing && (
        <div
          style={{
            position: "absolute",
            bottom: 14,
            right: 16,
            background: "var(--muted)",
            borderRadius: 100,
            padding: "3px 10px",
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            fontSize: 11,
            fontWeight: 600,
            color: "var(--muted-foreground)",
            letterSpacing: "0.05em",
            textTransform: "uppercase",
          }}
        >
          Indexing…
        </div>
      )}
    </Link>
  )
}

