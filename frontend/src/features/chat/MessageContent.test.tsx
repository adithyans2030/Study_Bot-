import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { TooltipProvider } from "@/components/ui/tooltip"
import { MessageContent } from "./MessageContent"
import type { Source } from "./types"

// Only CitationChip's tooltip needs a provider — the full app provider stack (theming, routing,
// query client) is irrelevant to this component and would only make "does it render raw HTML"
// checks harder to scope correctly (next-themes renders its own legitimate inline <script>).
function renderMessage(text: string, sources: Source[], onCiteClick: (n: number) => void) {
  return render(
    <TooltipProvider>
      <MessageContent text={text} sources={sources} onCiteClick={onCiteClick} />
    </TooltipProvider>,
  )
}

const source: Source = {
  n: 1,
  title: "Unit 2 Quick Revision",
  type: "pdf",
  location: "p.3",
  url: null,
  header: "Unit 2 › Edge detection",
  snippet: "The Sobel operator approximates the gradient...",
}

describe("MessageContent", () => {
  it("renders a citation as a focusable, labeled chip and calls back on click", async () => {
    const onCiteClick = vi.fn()
    renderMessage("Sobel detects edges [1].", [source], onCiteClick)

    const chip = screen.getByRole("button", { name: "Source 1: Unit 2 Quick Revision, p.3" })
    await userEvent.click(chip)
    expect(onCiteClick).toHaveBeenCalledWith(1)
  })

  it("disables a citation chip when its source wasn't provided (e.g. a refused answer)", () => {
    renderMessage("See [1].", [], vi.fn())
    expect(screen.getByRole("button", { name: "Source 1" })).toBeDisabled()
  })

  it("never interprets answer text as HTML, even text that looks like a script tag", () => {
    const { container } = renderMessage("<script>alert(1)</script>", [], vi.fn())
    expect(screen.getByText("<script>alert(1)</script>")).toBeInTheDocument()
    expect(container.querySelector("script")).toBeNull()
  })

  it("renders headings, bold text and lists", () => {
    renderMessage("# Summary\n**Key** point\n\n- one\n- two", [], vi.fn())
    expect(screen.getByRole("heading", { name: "Summary" })).toBeInTheDocument()
    expect(screen.getByText("Key")).toBeInTheDocument()
    expect(screen.getAllByRole("listitem")).toHaveLength(2)
  })
})
