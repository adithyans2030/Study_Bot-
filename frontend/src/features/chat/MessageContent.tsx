import { Fragment } from "react"
import type { Block, InlineToken } from "@/lib/rich"
import { parseRich } from "@/lib/rich"
import { CitationChip } from "./CitationChip"
import type { Source } from "./types"

/** Renders the parsed block/inline structure as JSX text nodes — never `dangerouslySetInnerHTML`
 * — so answer text (which may echo untrusted document content) can't inject markup. See rich.ts. */
export function MessageContent({
  text,
  sources,
  onCiteClick,
}: {
  text: string
  sources: Source[]
  onCiteClick: (n: number) => void
}) {
  const blocks = parseRich(text)
  const bySources = new Map(sources.map((s) => [s.n, s]))

  return (
    <div
      className="max-w-none space-y-3"
      style={{ fontSize: "var(--font-size-reading)", lineHeight: "var(--leading-reading)" }}
    >
      {blocks.map((block, i) => (
        <BlockNode key={i} block={block} sources={bySources} onCiteClick={onCiteClick} />
      ))}
    </div>
  )
}

function BlockNode({
  block,
  sources,
  onCiteClick,
}: {
  block: Block
  sources: Map<number, Source>
  onCiteClick: (n: number) => void
}) {
  switch (block.type) {
    case "h":
      return <h3 className="text-lg font-semibold">{inline(block.inline, sources, onCiteClick)}</h3>
    case "p":
      return <p>{inline(block.inline, sources, onCiteClick)}</p>
    case "ul":
      return (
        <ul className="list-disc space-y-1 pl-5">
          {block.items.map((item, i) => (
            <li key={i}>{inline(item, sources, onCiteClick)}</li>
          ))}
        </ul>
      )
    case "ol":
      return (
        <ol className="list-decimal space-y-1 pl-5">
          {block.items.map((item, i) => (
            <li key={i}>{inline(item, sources, onCiteClick)}</li>
          ))}
        </ol>
      )
    case "pre":
      return (
        <pre className="bg-muted overflow-x-auto rounded-md p-3 text-sm">
          <code style={{ fontFamily: "var(--font-mono)" }}>{block.text}</code>
        </pre>
      )
    case "table":
      return (
        <div className="overflow-x-auto">
          <table className="border-border w-full border-collapse text-sm">
            {block.head && (
              <thead>
                <tr>
                  {block.head.map((cell, i) => (
                    <th
                      key={i}
                      className="border-border bg-muted border px-2 py-1.5 text-left font-medium"
                    >
                      {inline(cell, sources, onCiteClick)}
                    </th>
                  ))}
                </tr>
              </thead>
            )}
            <tbody>
              {block.rows.map((row, i) => (
                <tr key={i}>
                  {row.map((cell, j) => (
                    <td key={j} className="border-border border px-2 py-1.5">
                      {inline(cell, sources, onCiteClick)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )
  }
}

function inline(
  tokens: InlineToken[],
  sources: Map<number, Source>,
  onCiteClick: (n: number) => void,
) {
  return tokens.map((token, i) => {
    switch (token.t) {
      case "text":
        return <Fragment key={i}>{token.v}</Fragment>
      case "strong":
        return <strong key={i}>{token.v}</strong>
      case "code":
        return (
          <code
            key={i}
            className="bg-muted rounded-sm px-1 py-0.5 text-[0.9em]"
            style={{ fontFamily: "var(--font-mono)" }}
          >
            {token.v}
          </code>
        )
      case "cite":
        return (
          <CitationChip
            key={i}
            n={token.n}
            source={sources.get(token.n)}
            onClick={() => onCiteClick(token.n)}
          />
        )
    }
  })
}
