import { FolderPlus, Plus } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { ConfirmDialog } from "@/design-system/ConfirmDialog"
import { useAuthStatus } from "@/features/auth/hooks"
import { useActiveJobs } from "@/features/jobs/hooks"
import { AddMaterialDialog } from "@/features/library/AddMaterialDialog"
import { CollectionCard } from "@/features/library/CollectionCard"
import { useCollections, useDeleteCollection } from "@/features/library/hooks"
import { NewCollectionDialog } from "@/features/library/NewCollectionDialog"
import { UploadQueueList } from "@/features/library/UploadQueueList"
import { useUploadQueue } from "@/features/library/useUploadQueue"

const SB_GREEN = "var(--primary)"
const SB_BORDER = "var(--border)"
const SB_MUTED = "var(--muted-foreground)"

function greeting(): string {
  const hour = new Date().getHours()
  if (hour < 5) return "Still up"
  if (hour < 12) return "Good morning"
  if (hour < 18) return "Good afternoon"
  return "Good evening"
}

export function DashboardPage() {
  const { data: authStatus } = useAuthStatus()
  const collections = useCollections()
  const activeJobs = useActiveJobs()
  const deleteCollection = useDeleteCollection()
  const uploadQueue = useUploadQueue()

  const [addOpen, setAddOpen] = useState(false)
  const [newCollectionOpen, setNewCollectionOpen] = useState(false)
  const [deleting, setDeleting] = useState<{ id: number; name: string } | null>(null)

  const processingCollections = new Set(
    (activeJobs.data ?? [])
      .filter((j) => j.status === "pending" || j.status === "running")
      .map((j) => j.collection),
  )

  const totalDocs = collections.data?.reduce((s, c) => s + c.documents, 0) ?? 0
  const totalSubjects = collections.data?.length ?? 0

  return (
    <div
      style={{
        maxWidth: 960,
        margin: "0 auto",
        padding: "32px 20px 80px",
        fontFamily: "'Georgia','Times New Roman',serif",
      }}
    >
      {/* ── OVERVIEW HEADER ── */}
      <header
        style={{
          display: "flex",
          flexWrap: "wrap",
          alignItems: "flex-start",
          justifyContent: "space-between",
          gap: 20,
          marginBottom: 40,
        }}
      >
        <div>
          <p
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.12em",
              color: SB_MUTED,
              textTransform: "uppercase",
              marginBottom: 10,
            }}
          >
            Overview
          </p>
          <h1
            style={{
              fontFamily: "'Georgia',serif",
              fontSize: "clamp(1.8rem,4vw,2.6rem)",
              fontWeight: 700,
              lineHeight: 1.15,
              letterSpacing: "-0.025em",
              color: "var(--foreground)",
              marginBottom: 8,
            }}
          >
            {greeting()}
            {authStatus?.user ? `, ${authStatus.user.username}.` : "."}
          </h1>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED }}>
            A small view of what is on your desk, and what you might pick up next.
          </p>
        </div>

        <Button
          onClick={() => setNewCollectionOpen(true)}
          style={{
            background: SB_GREEN,
            color: "var(--primary-foreground)",
            border: "none",
            borderRadius: 10,
            padding: "10px 20px",
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            fontSize: 14,
            fontWeight: 600,
            cursor: "pointer",
            display: "flex",
            alignItems: "center",
            gap: 8,
            boxShadow: "0 2px 10px rgba(30,77,63,0.2)",
            flexShrink: 0,
          }}
        >
          <Plus style={{ width: 16, height: 16 }} /> New subject
        </Button>
      </header>

      {/* ── STAT CARDS ── */}
      <div
        style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fit, minmax(180px, 1fr))",
          gap: 16,
          marginBottom: 52,
        }}
      >
        <StatCard
          icon="🗂️"
          value={collections.isPending ? "—" : String(totalSubjects)}
          label="subjects"
        />
        <StatCard
          icon="📄"
          value={collections.isPending ? "—" : String(totalDocs)}
          label="notes added"
        />
      </div>

      <UploadQueueList
        items={uploadQueue.items}
        onCancel={uploadQueue.cancel}
        onDismiss={uploadQueue.dismiss}
        onJobUpdate={uploadQueue.onJobUpdate}
      />

      {/* ── YOUR SUBJECTS ── */}
      <div style={{ marginBottom: 20, display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 16, flexWrap: "wrap" }}>
        <div>
          <p
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.12em",
              color: SB_MUTED,
              textTransform: "uppercase",
              marginBottom: 8,
            }}
          >
            Your subjects
          </p>
          <h2
            style={{
              fontFamily: "'Georgia',serif",
              fontSize: "clamp(1.3rem,2.5vw,1.8rem)",
              fontWeight: 700,
              color: "var(--foreground)",
              letterSpacing: "-0.02em",
            }}
          >
            Where your attention lives.
          </h2>
        </div>
        {totalSubjects > 0 && (
          <span
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 12,
              color: SB_MUTED,
              letterSpacing: "0.06em",
              textTransform: "uppercase",
              fontWeight: 600,
            }}
          >
            {totalSubjects} active
          </span>
        )}
      </div>

      {/* Collection grid */}
      {collections.isPending ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 20 }}>
          {[0, 1, 2].map((i) => <Skeleton key={i} className="h-36 rounded-xl" />)}
        </div>
      ) : collections.data && collections.data.length > 0 ? (
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(240px, 1fr))", gap: 20 }}>
          {collections.data.map((collection) => (
            <CollectionCard
              key={collection.id}
              collection={collection}
              processing={processingCollections.has(collection.name)}
              onDelete={() => setDeleting({ id: collection.id, name: collection.name })}
            />
          ))}
          {/* Add new card */}
          <button
            onClick={() => setNewCollectionOpen(true)}
            style={{
              background: "transparent",
              border: `2px dashed ${SB_BORDER}`,
              borderRadius: 16,
              padding: "28px 20px",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 10,
              cursor: "pointer",
              minHeight: 140,
              transition: "border-color 0.2s, background 0.2s",
              fontFamily: "'Georgia',serif",
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = SB_GREEN
              e.currentTarget.style.background = "rgba(30,77,63,0.03)"
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = SB_BORDER
              e.currentTarget.style.background = "transparent"
            }}
          >
            <div
              style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                background: "var(--muted)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontSize: 20,
                color: SB_MUTED,
              }}
            >
              +
            </div>
            <div style={{ textAlign: "center" }}>
              <p style={{ fontFamily: "'Georgia',serif", fontSize: 14, fontWeight: 700, color: "var(--foreground)", marginBottom: 4 }}>
                Make room for another
              </p>
              <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_MUTED }}>
                Add a new subject
              </p>
            </div>
          </button>
        </div>
      ) : (
        <div
          style={{
            border: `2px dashed ${SB_BORDER}`,
            borderRadius: 16,
            padding: "56px 20px",
            textAlign: "center",
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: 16,
          }}
        >
          <div style={{ width: 52, height: 52, borderRadius: "50%", background: "var(--muted)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 24 }}>
            🗂️
          </div>
          <div>
            <p style={{ fontFamily: "'Georgia',serif", fontSize: 18, fontWeight: 700, color: "var(--foreground)", marginBottom: 6 }}>
              Nothing here yet
            </p>
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED, maxWidth: 300 }}>
              Start by adding your notes — a subject is created for you automatically.
            </p>
          </div>
          <button
            onClick={() => setAddOpen(true)}
            style={{
              background: SB_GREEN,
              color: "var(--primary-foreground)",
              border: "none",
              borderRadius: 10,
              padding: "11px 24px",
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 14,
              fontWeight: 600,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
          >
            <FolderPlus style={{ width: 16, height: 16 }} /> Add material
          </button>
        </div>
      )}

      <AddMaterialDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        onUpload={(files, collection) => {
          for (const file of files) uploadQueue.start(file, collection)
        }}
      />
      <NewCollectionDialog open={newCollectionOpen} onOpenChange={setNewCollectionOpen} />
      <ConfirmDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.name}"?`}
        description="This permanently deletes the collection and every document in it. This can't be undone."
        onConfirm={() => {
          if (deleting) deleteCollection.mutate(deleting.id)
          setDeleting(null)
        }}
      />
    </div>
  )
}

function StatCard({ icon, value, label }: { icon: string; value: string; label: string }) {
  return (
    <div
      style={{
        background: "var(--card)",
        border: "1px solid var(--border)",
        borderRadius: 16,
        padding: "24px 24px 20px",
        display: "flex",
        flexDirection: "column",
        gap: 8,
      }}
    >
      <span style={{ fontSize: 22 }} aria-hidden>{icon}</span>
      <span style={{ fontFamily: "'Georgia',serif", fontSize: "clamp(1.8rem,3vw,2.4rem)", fontWeight: 700, color: "var(--foreground)", lineHeight: 1 }}>
        {value}
      </span>
      <span style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: "var(--muted-foreground)" }}>
        {label}
      </span>
    </div>
  )
}

