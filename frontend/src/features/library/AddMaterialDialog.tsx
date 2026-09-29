import { Loader2, Plus, SquarePlay } from "lucide-react"
import { useState } from "react"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { ApiError } from "@/lib/api"
import { Dropzone } from "./Dropzone"
import { useAddYoutube, useCollections } from "./hooks"

const NEW_COLLECTION = "__new__"

export function AddMaterialDialog({
  open,
  onOpenChange,
  onUpload,
  defaultCollection,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  onUpload: (files: File[], collection: string) => void
  defaultCollection?: string
}) {
  const collections = useCollections()
  const addYoutube = useAddYoutube()
  const [selected, setSelected] = useState<string>(defaultCollection ?? NEW_COLLECTION)
  const [newName, setNewName] = useState("")
  const [youtubeUrl, setYoutubeUrl] = useState("")

  const collection = selected === NEW_COLLECTION ? newName.trim() : selected
  const canProceed = collection.length > 0

  const close = (nextOpen: boolean) => {
    onOpenChange(nextOpen)
    if (!nextOpen) {
      setYoutubeUrl("")
      addYoutube.reset()
    }
  }

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add material</DialogTitle>
          <DialogDescription>Upload files or add a YouTube video with captions.</DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="upload-collection">Collection</Label>
            <Select value={selected} onValueChange={setSelected}>
              <SelectTrigger id="upload-collection" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {collections.data?.map((c) => (
                  <SelectItem key={c.id} value={c.name}>
                    {c.name}
                  </SelectItem>
                ))}
                <SelectItem value={NEW_COLLECTION}>
                  <Plus className="size-4" /> New collection
                </SelectItem>
              </SelectContent>
            </Select>
            {selected === NEW_COLLECTION && (
              <Input
                autoFocus
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="e.g. Operating Systems"
                maxLength={60}
                aria-label="New collection name"
              />
            )}
          </div>

          <Dropzone
            disabled={!canProceed}
            disabledHint="Name a collection above first"
            onFiles={(files) => {
              onUpload(files, collection)
              close(false)
            }}
          />

          <div className="flex items-center gap-3">
            <div className="bg-border h-px flex-1" />
            <span className="text-muted-foreground text-xs">or</span>
            <div className="bg-border h-px flex-1" />
          </div>

          <form
            className="space-y-2"
            onSubmit={(e) => {
              e.preventDefault()
              if (!canProceed || !youtubeUrl.trim()) return
              addYoutube.mutate(
                { url: youtubeUrl.trim(), collection },
                { onSuccess: () => close(false) },
              )
            }}
          >
            <Label htmlFor="youtube-url">YouTube link</Label>
            <div className="flex gap-2">
              <div className="relative flex-1">
                <SquarePlay className="text-muted-foreground absolute top-1/2 left-3 size-4 -translate-y-1/2" />
                <Input
                  id="youtube-url"
                  className="pl-9"
                  placeholder="https://www.youtube.com/watch?v=..."
                  value={youtubeUrl}
                  onChange={(e) => setYoutubeUrl(e.target.value)}
                  disabled={!canProceed}
                />
              </div>
              <Button
                type="submit"
                disabled={!canProceed || !youtubeUrl.trim() || addYoutube.isPending}
              >
                {addYoutube.isPending && <Loader2 className="animate-spin" />}
                Add
              </Button>
            </div>
            {addYoutube.error && (
              <p role="alert" className="text-destructive text-sm">
                {addYoutube.error instanceof ApiError
                  ? addYoutube.error.message
                  : "Couldn't add that video."}
              </p>
            )}
            <p className="text-muted-foreground text-xs">
              Needs English captions (auto-generated is fine).
            </p>
          </form>
        </div>
      </DialogContent>
    </Dialog>
  )
}
