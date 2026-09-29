import { ArrowLeft, Brain, Layers, MessageSquare, Plus } from "lucide-react"
import { useState } from "react"
import { Link, Navigate, useParams } from "react-router-dom"
import { Skeleton } from "@/components/ui/skeleton"
import { ConfirmDialog } from "@/design-system/ConfirmDialog"
import { colorForCollection, collectionColorVar } from "@/design-system/collection-colors"
import { useActiveJobs } from "@/features/jobs/hooks"
import { AddMaterialDialog } from "./AddMaterialDialog"
import { DocumentRow } from "./DocumentRow"
import { useCollections, useDeleteDocument, useDocuments, useReindexDocument } from "./hooks"
import { UploadQueueList } from "./UploadQueueList"
import { useUploadQueue } from "./useUploadQueue"

const SB_GREEN = "var(--primary)"
const SB_BORDER = "var(--border)"
const SB_MUTED = "var(--muted-foreground)"

export function CollectionDetailPage() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const collections = useCollections()
  const collection = collections.data?.find((c) => c.id === Number(collectionId))
  const documents = useDocuments(collection?.name)
  const activeJobs = useActiveJobs()
  const deleteDocument = useDeleteDocument()
  const reindexDocument = useReindexDocument()
  const uploadQueue = useUploadQueue()
  const [addOpen, setAddOpen] = useState(false)
  const [deleting, setDeleting] = useState<{ id: number; title: string } | null>(null)

  const reindexingIds = new Set(
    (activeJobs.data ?? [])
      .filter((j) => (j.status === "pending" || j.status === "running") && j.kind === "reindex")
      .map((j) => j.document_id)
      .filter((id): id is number => id !== null),
  )

  if (collections.isSuccess && !collection) return <Navigate to="/app" replace />

  const color = collection ? collectionColorVar(colorForCollection(collection.id)) : SB_GREEN
  const initial = collection ? collection.name.charAt(0).toUpperCase() : "?"

  return (
    <div
      style={{
        maxWidth: 960,
        margin: "0 auto",
        padding: "28px 20px 80px",
        fontFamily: "'Georgia','Times New Roman',serif",
      }}
    >
      {/* Back link */}
      <Link
        to="/app"
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 6,
          fontFamily: "ui-sans-serif,system-ui,sans-serif",
          fontSize: 13,
          color: SB_MUTED,
          textDecoration: "none",
          marginBottom: 24,
          letterSpacing: "0.02em",
        }}
      >
        <ArrowLeft style={{ width: 14, height: 14 }} /> Back to overview
      </Link>

      {/* Subject header card */}
      <div
        style={{
          background: "var(--card)",
          border: `1px solid ${SB_BORDER}`,
          borderRadius: 16,
          padding: "24px 28px",
          marginBottom: 28,
          borderTop: `3px solid ${color}`,
        }}
      >
        {collection ? (
          <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", justifyContent: "space-between", gap: 20 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
              {/* Letter avatar */}
              <div
                style={{
                  width: 52,
                  height: 52,
                  borderRadius: 14,
                  background: color,
                  color: "#fff",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  fontFamily: "'Georgia',serif",
                  fontWeight: 700,
                  fontSize: 24,
                  flexShrink: 0,
                }}
                aria-hidden
              >
                {initial}
              </div>
              <div>
                <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", color: SB_MUTED, textTransform: "uppercase", marginBottom: 6 }}>
                  Subject workspace
                </p>
                <h1 style={{ fontFamily: "'Georgia',serif", fontSize: "clamp(1.5rem,3vw,2.2rem)", fontWeight: 700, color: "var(--foreground)", lineHeight: 1.2, letterSpacing: "-0.02em" }}>
                  {collection.name}
                </h1>
                <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, marginTop: 4 }}>
                  {collection.documents} document{collection.documents === 1 ? "" : "s"} Â· {collection.chunks} passages
                </p>
              </div>
            </div>

            {/* Actions */}
            <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
              <Link
                to={`/app/c/${collection.id}/study`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--foreground)",
                  background: "var(--card)",
                  border: `1px solid ${SB_BORDER}`,
                  borderRadius: 10,
                  padding: "9px 18px",
                  textDecoration: "none",
                  transition: "background 0.2s",
                }}
              >
                <Brain style={{ width: 15, height: 15, color: "var(--primary)" }} /> Study Center
              </Link>
              <Link
                to={`/app/knowledge?collection=${collection.id}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--foreground)",
                  background: "var(--card)",
                  border: `1px solid ${SB_BORDER}`,
                  borderRadius: 10,
                  padding: "9px 18px",
                  textDecoration: "none",
                  transition: "background 0.2s",
                }}
              >
                <Layers style={{ width: 15, height: 15, color: "var(--primary)" }} /> Knowledge Graph
              </Link>
              <Link
                to={`/app/chat?collection=${encodeURIComponent(collection.name)}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: SB_GREEN,
                  background: "rgba(30,77,63,0.07)",
                  border: `1px solid rgba(30,77,63,0.2)`,
                  borderRadius: 10,
                  padding: "9px 18px",
                  textDecoration: "none",
                  transition: "background 0.2s",
                }}
              >
                <MessageSquare style={{ width: 15, height: 15 }} /> Ask
              </Link>
              <button
                onClick={() => setAddOpen(true)}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 14,
                  fontWeight: 600,
                  color: "var(--primary-foreground)",
                  background: SB_GREEN,
                  border: "none",
                  borderRadius: 10,
                  padding: "9px 18px",
                  cursor: "pointer",
                  boxShadow: "0 2px 8px rgba(30,77,63,0.2)",
                }}
              >
                <Plus style={{ width: 15, height: 15 }} /> Add material
              </button>
            </div>
          </div>
        ) : (
          <Skeleton className="h-14 w-72" />
        )}
      </div>

      <UploadQueueList
        items={uploadQueue.items}
        onCancel={uploadQueue.cancel}
        onDismiss={uploadQueue.dismiss}
        onJobUpdate={uploadQueue.onJobUpdate}
      />

      {/* Two-column layout: notes left, tutor right */}
      <div
        style={{
          display: "grid",
          gap: 20,
        }}
        className="grid-cols-1 lg:grid-cols-[1fr_280px]"
      >
        {/* Notes panel */}
        <div
          style={{
            background: "var(--card)",
            border: `1px solid ${SB_BORDER}`,
            borderRadius: 16,
            padding: "24px 24px 28px",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20, flexWrap: "wrap", gap: 12 }}>
            <div>
              <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", color: SB_MUTED, textTransform: "uppercase", marginBottom: 8 }}>
                Your notes
              </p>
              <h2 style={{ fontFamily: "'Georgia',serif", fontSize: "clamp(1.2rem,2vw,1.5rem)", fontWeight: 700, color: "var(--foreground)" }}>
                Start with what you know.
              </h2>
            </div>
            {documents.data && documents.data.length > 0 && (
              <span style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_GREEN, fontWeight: 600, background: "rgba(30,77,63,0.07)", border: `1px solid rgba(30,77,63,0.15)`, padding: "4px 12px", borderRadius: 100 }}>
                {documents.data.length} saved
              </span>
            )}
          </div>

          {documents.isPending ? (
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {[0, 1, 2].map((i) => <Skeleton key={i} className="h-16 rounded-lg" />)}
            </div>
          ) : documents.data && documents.data.length > 0 ? (
            <ul style={{ display: "flex", flexDirection: "column", gap: 8, listStyle: "none", margin: 0, padding: 0 }}>
              {documents.data.map((doc) => (
                <DocumentRow
                  key={doc.id}
                  document={doc}
                  reindexing={reindexingIds.has(doc.id)}
                  onReindex={() => reindexDocument.mutate(doc.id)}
                  onDelete={() => setDeleting({ id: doc.id, title: doc.title })}
                />
              ))}
            </ul>
          ) : (
            <div style={{ border: `2px dashed ${SB_BORDER}`, borderRadius: 12, padding: "36px 20px", textAlign: "center" }}>
              <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED }}>
                No documents in this collection yet.
              </p>
              <button
                onClick={() => setAddOpen(true)}
                style={{
                  marginTop: 16,
                  background: SB_GREEN,
                  color: "var(--primary-foreground)",
                  border: "none",
                  borderRadius: 8,
                  padding: "8px 18px",
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 13,
                  fontWeight: 600,
                  cursor: "pointer",
                }}
              >
                Upload your first note
              </button>
            </div>
          )}

          {/* Upload icon */}
          {documents.data && documents.data.length > 0 && (
            <div style={{ display: "flex", justifyContent: "center", marginTop: 20 }}>
              <button
                onClick={() => setAddOpen(true)}
                style={{
                  background: "transparent",
                  border: `1px solid ${SB_BORDER}`,
                  borderRadius: 8,
                  padding: "8px 16px",
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontSize: 12,
                  color: SB_MUTED,
                  cursor: "pointer",
                  display: "flex",
                  alignItems: "center",
                  gap: 6,
                }}
              >
                <Plus style={{ width: 13, height: 13 }} /> Add more
              </button>
            </div>
          )}
        </div>

        {/* Tutor panel */}
        <div
          style={{
            background: "var(--card)",
            border: `1px solid ${SB_BORDER}`,
            borderRadius: 16,
            padding: "24px",
            display: "flex",
            flexDirection: "column",
            gap: 16,
          }}
        >
          <div>
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 10, fontWeight: 600, letterSpacing: "0.12em", color: SB_MUTED, textTransform: "uppercase", marginBottom: 8 }}>
              Source-grounded tutor
            </p>
            <h2 style={{ fontFamily: "'Georgia',serif", fontSize: 18, fontWeight: 700, color: "var(--foreground)", lineHeight: 1.3 }}>
              Ask what your notes can support.
            </h2>
          </div>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, lineHeight: 1.65 }}>
            Answers stay close to your uploaded material and show the page or slide used.
          </p>
          <div
            style={{
              background: "var(--muted)",
              border: `1px dashed ${SB_BORDER}`,
              borderRadius: 10,
              padding: "16px",
            }}
          >
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_MUTED, lineHeight: 1.6, fontStyle: "italic" }}>
              {documents.data && documents.data.length > 0
                ? "Answers are grounded only in the notes uploaded to this subject."
                : "Upload a readable note first. The tutor only answers from sources in this subject."}
            </p>
          </div>
          {collection && (
            <Link
              to={`/app/chat?collection=${encodeURIComponent(collection.name)}`}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                fontFamily: "ui-sans-serif,system-ui,sans-serif",
                fontSize: 14,
                fontWeight: 600,
                color: "var(--primary-foreground)",
                background: SB_GREEN,
                textDecoration: "none",
                borderRadius: 10,
                padding: "11px 20px",
                boxShadow: "0 2px 8px rgba(30,77,63,0.2)",
                marginTop: "auto",
              }}
            >
              <MessageSquare style={{ width: 15, height: 15 }} /> Open tutor
            </Link>
          )}
        </div>
      </div>

      {collection && (
        <AddMaterialDialog
          open={addOpen}
          onOpenChange={setAddOpen}
          defaultCollection={collection.name}
          onUpload={(files) => {
            for (const file of files) uploadQueue.start(file, collection.name)
          }}
        />
      )}
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.title}"?`}
        description="This removes it from your library. This can't be undone."
        onConfirm={() => {
          if (deleting) deleteDocument.mutate(deleting.id)
          setDeleting(null)
        }}
      />
    </div>
  )
}


