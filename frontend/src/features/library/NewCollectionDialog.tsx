import { Loader2 } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { useCreateCollection } from "./hooks"

export function NewCollectionDialog({
  open,
  onOpenChange,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
}) {
  const [name, setName] = useState("")
  const create = useCreateCollection()

  const close = (nextOpen: boolean) => {
    onOpenChange(nextOpen)
    if (!nextOpen) {
      setName("")
      create.reset()
    }
  }

  const submit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!name.trim()) return
    create.mutate(name.trim(), { onSuccess: () => close(false) })
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent>
        <form onSubmit={submit}>
          <DialogHeader>
            <DialogTitle>New collection</DialogTitle>
            <DialogDescription>
              A collection groups notes for one subject or course.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-1.5 py-4">
            <Label htmlFor="collection-name">Name</Label>
            <Input
              id="collection-name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Operating Systems"
              maxLength={60}
            />
            {create.error && (
              <p role="alert" className="text-destructive text-sm">
                {create.error instanceof ApiError
                  ? create.error.message
                  : "Couldn't create that collection."}
              </p>
            )}
          </div>
          <DialogFooter>
            <Button type="submit" disabled={!name.trim() || create.isPending}>
              {create.isPending && <Loader2 className="animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
