import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { useCollections } from "@/features/library/hooks"

const ALL = "__all__"

export function CollectionFilter({
  value,
  onChange,
}: {
  value: string | null
  onChange: (value: string | null) => void
}) {
  const collections = useCollections()

  return (
    <Select value={value ?? ALL} onValueChange={(v) => onChange(v === ALL ? null : v)}>
      <SelectTrigger size="sm" aria-label="Which collection to search" className="w-auto">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>All collections</SelectItem>
        {collections.data?.map((c) => (
          <SelectItem key={c.id} value={c.name}>
            {c.name}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  )
}
