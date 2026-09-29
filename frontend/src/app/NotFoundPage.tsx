import { Link } from "react-router-dom"
import { Button } from "@/components/ui/button"

export function NotFoundPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-4 p-6 text-center">
      <p className="text-muted-foreground text-sm font-medium">404</p>
      <h1 className="text-xl font-semibold">This page doesn't exist</h1>
      <Button asChild>
        <Link to="/">Back to StudyBot</Link>
      </Button>
    </div>
  )
}
