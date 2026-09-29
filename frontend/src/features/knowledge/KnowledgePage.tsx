import { useState } from "react"
import { Brain, Search, Download, X } from "lucide-react"
import { useSearchParams } from "react-router-dom"
import { useCollections } from "@/features/library/hooks"
import {
  useKnowledgeNodes,
  useKnowledgeSearch,
  useKnowledgeStats,
  exportZipUrl,
  type KnowledgeNode,
} from "./api"

const SB_GREEN = "var(--primary)"
const SB_BORDER = "var(--border)"
const SB_MUTED = "var(--muted-foreground)"

const TYPE_COLORS: Record<string, string> = {
  concept:    "#7c5cfc",
  definition: "#22d3a0",
  procedure:  "#f97316",
  formula:    "#f5c542",
  example:    "#60a5fa",
  summary:    "#ff5c7c",
}

const TYPE_ICONS: Record<string, string> = {
  concept: "💡", definition: "📖", procedure: "⚙️",
  formula: "∑", example: "🔍", summary: "📋",
}

interface Props {
  collectionId?: number
  collectionName?: string
}

export function KnowledgePage(props: Props) {
  const [searchParams] = useSearchParams()
  const paramCollection = searchParams.get("collection")
  const collectionId = props.collectionId ?? (paramCollection ? Number(paramCollection) : undefined)

  const collections = useCollections()
  const collectionName =
    props.collectionName ?? collections.data?.find((c) => c.id === collectionId)?.name

  const [search, setSearch] = useState("")
  const [filterType, setFilterType] = useState("")
  const [selected, setSelected] = useState<KnowledgeNode | null>(null)

  const stats = useKnowledgeStats(collectionId)
  const nodes = useKnowledgeNodes(collectionId, filterType || undefined)
  const searchResults = useKnowledgeSearch(search, collectionId)

  const display = search.trim().length > 2
    ? (searchResults.data ?? []).map((r) => ({ ...r }))
    : (nodes.data ?? [])

  return (
    <div style={{ padding: "28px 24px", maxWidth: 1100, margin: "0 auto" }}>
      {/* Header */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 24, flexWrap: "wrap", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ width: 40, height: 40, borderRadius: 12, background: "rgba(124,92,252,0.12)", display: "flex", alignItems: "center", justifyContent: "center" }}>
            <Brain style={{ width: 20, height: 20, color: TYPE_COLORS.concept }} />
          </div>
          <div>
            <h1 style={{ fontFamily: "'Georgia',serif", fontSize: 22, fontWeight: 700, color: "var(--foreground)", margin: 0 }}>
              Knowledge Graph
            </h1>
            {collectionName && (
              <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_MUTED, margin: 0 }}>
                {collectionName}
              </p>
            )}
          </div>
        </div>
        <a
          href={exportZipUrl(collectionId)}
          download
          style={{ display: "flex", alignItems: "center", gap: 6, background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 8, padding: "7px 14px", fontSize: 13, fontFamily: "ui-sans-serif,system-ui,sans-serif", color: "var(--foreground)", textDecoration: "none", fontWeight: 500 }}
        >
          <Download style={{ width: 14, height: 14 }} /> Export ZIP
        </a>
      </div>

      {/* Stats row */}
      {stats.data && (
        <div style={{ display: "flex", gap: 12, marginBottom: 24, flexWrap: "wrap" }}>
          <StatCard value={stats.data.total_nodes} label="Knowledge nodes" color={TYPE_COLORS.concept} />
          <StatCard value={stats.data.documents_covered} label="Documents covered" color={SB_GREEN} />
          {Object.entries(stats.data.nodes_by_type).map(([type, count]) => (
            <StatCard key={type} value={count} label={type + "s"} color={TYPE_COLORS[type] ?? SB_MUTED} />
          ))}
        </div>
      )}

      {/* Search + filter */}
      <div style={{ display: "flex", gap: 10, marginBottom: 20, flexWrap: "wrap" }}>
        <div style={{ flex: 1, minWidth: 200, position: "relative" }}>
          <Search style={{ position: "absolute", left: 10, top: "50%", transform: "translateY(-50%)", width: 15, height: 15, color: SB_MUTED }} />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search knowledge nodes..."
            style={{ width: "100%", paddingLeft: 34, paddingRight: 12, paddingTop: 8, paddingBottom: 8, borderRadius: 8, border: `1px solid ${SB_BORDER}`, background: "var(--card)", color: "var(--foreground)", fontSize: 13, fontFamily: "ui-sans-serif,system-ui,sans-serif", outline: "none", boxSizing: "border-box" }}
          />
        </div>
        <select
          value={filterType}
          onChange={(e) => setFilterType(e.target.value)}
          style={{ padding: "8px 12px", borderRadius: 8, border: `1px solid ${SB_BORDER}`, background: "var(--card)", color: "var(--foreground)", fontSize: 13, fontFamily: "ui-sans-serif,system-ui,sans-serif", cursor: "pointer" }}
        >
          <option value="">All types</option>
          {["concept","definition","procedure","formula","example","summary"].map((t) => (
            <option key={t} value={t}>{t.charAt(0).toUpperCase() + t.slice(1)}s</option>
          ))}
        </select>
      </div>

      {/* Nodes grid */}
      {nodes.isPending ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {[...Array(6)].map((_, i) => (
            <div key={i} style={{ height: 160, background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 14, animation: "pulse 1.5s ease-in-out infinite" }} />
          ))}
        </div>
      ) : display.length === 0 ? (
        <div style={{ textAlign: "center", padding: "60px 20px", background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 16 }}>
          <div style={{ fontSize: 40, marginBottom: 12 }}>🧠</div>
          <p style={{ fontFamily: "'Georgia',serif", fontSize: 18, fontWeight: 700, color: "var(--foreground)", marginBottom: 6 }}>
            {search ? "No nodes matched" : "No knowledge nodes yet"}
          </p>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED }}>
            {search ? "Try different search terms." : "Upload documents — StudyBot will extract concepts automatically."}
          </p>
        </div>
      ) : (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }}>
          {display.map((node) => (
            <NodeCard key={node.id} node={node} onClick={() => setSelected(node)} />
          ))}
        </div>
      )}

      {/* Detail modal */}
      {selected && (
        <div
          onClick={() => setSelected(null)}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.5)", zIndex: 100, display: "flex", alignItems: "center", justifyContent: "center", padding: 20 }}
        >
          <div
            onClick={(e) => e.stopPropagation()}
            style={{ background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 18, padding: 28, maxWidth: 600, width: "100%", maxHeight: "80vh", overflowY: "auto", position: "relative" }}
          >
            <button onClick={() => setSelected(null)} style={{ position: "absolute", top: 16, right: 16, background: "none", border: "none", cursor: "pointer", color: SB_MUTED }}>
              <X style={{ width: 18, height: 18 }} />
            </button>
            <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 16 }}>
              <span style={{ fontSize: 22 }}>{TYPE_ICONS[selected.type] ?? "📌"}</span>
              <div>
                <span style={{ fontSize: 11, fontWeight: 600, letterSpacing: "0.1em", textTransform: "uppercase", color: TYPE_COLORS[selected.type] ?? SB_MUTED, fontFamily: "ui-sans-serif,system-ui,sans-serif" }}>{selected.type}</span>
                <h2 style={{ fontFamily: "'Georgia',serif", fontSize: 20, fontWeight: 700, color: "var(--foreground)", margin: 0, lineHeight: 1.3 }}>{selected.title}</h2>
              </div>
            </div>
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, marginBottom: 16, fontStyle: "italic" }}>{selected.description}</p>
            <div style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: "var(--foreground)", lineHeight: 1.7, whiteSpace: "pre-wrap" }}>{selected.body}</div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6, marginTop: 16 }}>
              {selected.tags.map((t) => (
                <span key={t} style={{ background: "var(--muted)", border: `1px solid ${SB_BORDER}`, borderRadius: 100, padding: "2px 10px", fontSize: 11, fontFamily: "ui-sans-serif,system-ui,sans-serif", color: SB_MUTED }}>
                  {t}
                </span>
              ))}
            </div>
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 11, color: SB_MUTED, marginTop: 14 }}>
              From: {selected.source_document}
            </p>
          </div>
        </div>
      )}
    </div>
  )
}

function StatCard({ value, label, color }: { value: number; label: string; color: string }) {
  return (
    <div style={{ background: "var(--card)", border: `1px solid var(--border)`, borderRadius: 12, padding: "12px 16px", minWidth: 100 }}>
      <div style={{ fontSize: 22, fontWeight: 800, color, fontFamily: "ui-sans-serif,system-ui,sans-serif" }}>{value}</div>
      <div style={{ fontSize: 11, color: "var(--muted-foreground)", fontFamily: "ui-sans-serif,system-ui,sans-serif", marginTop: 2 }}>{label}</div>
    </div>
  )
}

function NodeCard({ node, onClick }: { node: KnowledgeNode; onClick: () => void }) {
  const color = TYPE_COLORS[node.type] ?? "#aaa"
  return (
    <div
      onClick={onClick}
      style={{ background: "var(--card)", border: `1px solid var(--border)`, borderRadius: 14, padding: 18, cursor: "pointer", transition: "box-shadow 0.15s, transform 0.15s", position: "relative", overflow: "hidden" }}
      onMouseEnter={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "0 4px 20px rgba(0,0,0,0.12)"; (e.currentTarget as HTMLDivElement).style.transform = "translateY(-2px)"; }}
      onMouseLeave={(e) => { (e.currentTarget as HTMLDivElement).style.boxShadow = "none"; (e.currentTarget as HTMLDivElement).style.transform = "none"; }}
    >
      <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: 3, background: color, borderRadius: "14px 14px 0 0" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 8, marginTop: 4 }}>
        <span style={{ fontSize: 11, fontWeight: 700, letterSpacing: "0.1em", textTransform: "uppercase", color, fontFamily: "ui-sans-serif,system-ui,sans-serif" }}>
          {TYPE_ICONS[node.type]} {node.type}
        </span>
      </div>
      <h3 style={{ fontFamily: "'Georgia',serif", fontSize: 15, fontWeight: 700, color: "var(--foreground)", margin: "0 0 6px", lineHeight: 1.35 }}>
        {node.title}
      </h3>
      <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: "var(--muted-foreground)", lineHeight: 1.5, margin: "0 0 10px", display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
        {node.description}
      </p>
      <div style={{ display: "flex", flexWrap: "wrap", gap: 4 }}>
        {node.tags.slice(0, 3).map((t) => (
          <span key={t} style={{ background: `${color}18`, color, borderRadius: 100, padding: "1px 8px", fontSize: 10, fontFamily: "ui-sans-serif,system-ui,sans-serif", fontWeight: 600 }}>
            {t}
          </span>
        ))}
      </div>
    </div>
  )
}
