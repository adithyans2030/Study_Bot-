import { useEffect, useState } from "react"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Checkbox } from "@/components/ui/checkbox"
import { Input } from "@/components/ui/input"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Switch } from "@/components/ui/switch"
import { Textarea } from "@/components/ui/textarea"
import { COLLECTION_COLORS, collectionColorVar } from "./collection-colors"
import { ThemeToggle } from "./ThemeToggle"

/** No Storybook (§3.E of the plan: real upkeep cost, no other contributors to hand a catalog to).
 * This route is the substitute — every foundation and core primitive state in one page you can
 * actually open, in either theme, on a phone or a desktop. Not shipped: excluded from the router
 * in production builds once real screens exist (see app/router.tsx). */
export function FoundationsPage() {
  const [apiStatus, setApiStatus] = useState<"checking" | "ok" | "down">("checking")

  useEffect(() => {
    fetch("/api/health")
      .then((r) => setApiStatus(r.ok ? "ok" : "down"))
      .catch(() => setApiStatus("down"))
  }, [])

  return (
    <div className="mx-auto max-w-4xl space-y-12 p-6 pb-24">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-semibold">StudyBot design foundations</h1>
          <p className="text-muted-foreground mt-1">
            Tokens and core primitives, reviewable without Storybook.
          </p>
        </div>
        <ThemeToggle />
      </header>

      <Section title="Backend connection (dev proxy)">
        <p className="text-sm">
          <code className="bg-muted rounded-sm px-1.5 py-0.5">GET /api/health</code> through the
          Vite dev proxy:{" "}
          <Badge
            variant={
              apiStatus === "ok" ? "default" : apiStatus === "down" ? "destructive" : "secondary"
            }
          >
            {apiStatus === "checking"
              ? "checking..."
              : apiStatus === "ok"
                ? "reachable"
                : "unreachable"}
          </Badge>
        </p>
      </Section>

      <Section title="Color">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {(
            [
              ["background", "foreground"],
              ["card", "card-foreground"],
              ["primary", "primary-foreground"],
              ["secondary", "secondary-foreground"],
              ["muted", "muted-foreground"],
              ["accent", "accent-foreground"],
              ["destructive", "destructive-foreground"],
              ["evidence", "evidence-foreground"],
            ] as const
          ).map(([bg, fg]) => (
            <Swatch key={bg} bgVar={bg} fgVar={fg} />
          ))}
        </div>
        <p className="text-muted-foreground mt-3 text-sm">
          Every pairing above is checked against WCAG AA (4.5:1) in{" "}
          <code className="bg-muted rounded-sm px-1.5 py-0.5">tokens.contrast.test.ts</code>.
        </p>
      </Section>

      <Section title="Collection colors">
        <div className="flex flex-wrap gap-3">
          {COLLECTION_COLORS.map((color) => (
            <div key={color} className="flex flex-col items-center gap-1.5">
              <div
                className="size-10 rounded-full"
                style={{ backgroundColor: collectionColorVar(color) }}
                aria-hidden
              />
              <span className="text-muted-foreground text-xs capitalize">{color}</span>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Type scale">
        <div className="space-y-2">
          <p className="text-xs">text-xs — The quick brown fox</p>
          <p className="text-sm">text-sm — The quick brown fox</p>
          <p className="text-base">text-base — The quick brown fox</p>
          <p className="text-lg">text-lg — The quick brown fox</p>
          <p className="text-xl">text-xl — The quick brown fox</p>
          <p className="text-2xl">text-2xl — The quick brown fox</p>
          <p className="text-3xl">text-3xl — The quick brown fox</p>
          <p style={{ fontSize: "var(--font-size-reading)", lineHeight: "var(--leading-reading)" }}>
            reading size — the size and line height answers stream in at, tuned for a long paragraph
            of study material rather than a UI label.
          </p>
        </div>
      </Section>

      <Section title="Buttons">
        <div className="flex flex-wrap items-center gap-3">
          <Button>Default</Button>
          <Button variant="outline">Outline</Button>
          <Button variant="secondary">Secondary</Button>
          <Button variant="ghost">Ghost</Button>
          <Button variant="destructive">Destructive</Button>
          <Button variant="link">Link</Button>
          <Button disabled>Disabled</Button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-3">
          <Button size="sm">Small</Button>
          <Button size="default">Default</Button>
          <Button size="lg">Large</Button>
          <Button size="icon" aria-label="Example icon button">
            <Badge className="sr-only">icon</Badge>+
          </Button>
        </div>
      </Section>

      <Section title="Form controls">
        <div className="grid max-w-sm gap-4">
          <Input placeholder="Ask a question about Computer Vision..." />
          <Textarea placeholder="Auto-growing textarea..." />
          <label className="flex items-center gap-2 text-sm">
            <Checkbox /> Use general knowledge
          </label>
          <label className="flex items-center gap-2 text-sm">
            <Switch /> Read answers aloud
          </label>
        </div>
      </Section>

      <Section title="Feedback & status">
        <div className="flex flex-wrap items-center gap-3">
          <Badge>Ready</Badge>
          <Badge variant="secondary">Processing</Badge>
          <Badge variant="destructive">Failed</Badge>
          <Badge variant="outline">Uploading 45%</Badge>
        </div>
        <div className="mt-4 max-w-sm space-y-3">
          <Progress value={62} />
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      </Section>

      <Section title="Card & avatar">
        <Card className="max-w-sm">
          <CardHeader>
            <CardTitle>Operating Systems</CardTitle>
          </CardHeader>
          <CardContent className="flex items-center gap-3">
            <Avatar>
              <AvatarFallback>OS</AvatarFallback>
            </Avatar>
            <div>
              <p className="text-sm font-medium">12 documents</p>
              <p className="text-muted-foreground text-xs">Last asked 2 hours ago</p>
            </div>
          </CardContent>
        </Card>
      </Section>

      <Section title="Citation chip (a preview of the evidence color)">
        <p className="text-sm">
          The minimum filter replaces a pixel with the darkest value in its neighborhood
          <CitationChip n={1} /> and is commonly used to suppress bright noise
          <CitationChip n={2} />.
        </p>
      </Section>
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h2 className="mb-3 text-lg font-semibold">{title}</h2>
      {children}
    </section>
  )
}

function Swatch({ bgVar, fgVar }: { bgVar: string; fgVar: string }) {
  return (
    <div
      className="rounded-lg border p-3 text-sm"
      style={{ backgroundColor: `var(--color-${bgVar})`, color: `var(--color-${fgVar})` }}
    >
      <div className="font-medium">{bgVar}</div>
      <div className="opacity-80">{fgVar}</div>
    </div>
  )
}

function CitationChip({ n }: { n: number }) {
  return (
    <button
      type="button"
      className="bg-evidence/15 text-evidence hover:bg-evidence/25 mx-0.5 inline-flex size-4 items-center justify-center rounded-sm align-super text-[10px] font-medium transition-colors"
      aria-label={`Source ${n}`}
    >
      {n}
    </button>
  )
}
