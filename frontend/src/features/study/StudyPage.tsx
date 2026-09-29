import { useState } from "react"
import {
  ArrowLeft,
  BookOpen,
  Brain,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Copy,
  HelpCircle,
  Layers,
  RotateCw,
  Sparkles,
  XCircle,
} from "lucide-react"
import { Link, useParams } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { useCollections } from "@/features/library/hooks"
import {
  type QuizQuestion,
  useGenerateFlashcards,
  useGenerateQuiz,
  useGenerateSummary,
} from "./api"

const SB_BORDER = "var(--border)"
const SB_MUTED = "var(--muted-foreground)"

export function StudyPage() {
  const { collectionId } = useParams<{ collectionId: string }>()
  const idNum = Number(collectionId)
  const collections = useCollections()
  const collection = collections.data?.find((c) => c.id === idNum)

  const [tab, setTab] = useState<"summary" | "quiz" | "flashcards">("summary")

  return (
    <div style={{ maxWidth: 840, margin: "0 auto", padding: "32px 20px 80px" }}>
      <div style={{ marginBottom: 24 }}>
        <Link
          to={`/app/c/${idNum}`}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 6,
            fontSize: 13,
            color: SB_MUTED,
            textDecoration: "none",
            marginBottom: 12,
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
          }}
        >
          <ArrowLeft style={{ width: 14, height: 14 }} /> Back to {collection?.name ?? "Collection"}
        </Link>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
          <div>
            <h1 style={{ fontFamily: "'Georgia',serif", fontSize: 26, fontWeight: 700, margin: "0 0 4px", color: "var(--foreground)" }}>
              Study Center
            </h1>
            <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, margin: 0 }}>
              AI-powered summaries, interactive quizzes, and flashcards generated directly from your materials.
            </p>
          </div>
          <Link to={`/app/knowledge?collection=${idNum}`}>
            <Button variant="outline" size="sm" className="gap-2">
              <Layers style={{ width: 14, height: 14 }} /> Open Knowledge Graph
            </Button>
          </Link>
        </div>
      </div>

      <div
        style={{
          display: "flex",
          gap: 8,
          borderBottom: `1px solid ${SB_BORDER}`,
          paddingBottom: 8,
          marginBottom: 28,
        }}
      >
        <button
          onClick={() => setTab("summary")}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            background: tab === "summary" ? "var(--primary)" : "transparent",
            color: tab === "summary" ? "var(--primary-foreground)" : "var(--foreground)",
            fontWeight: tab === "summary" ? 600 : 500,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            transition: "all 0.15s ease",
          }}
        >
          <BookOpen style={{ width: 15, height: 15 }} /> Summary
        </button>

        <button
          onClick={() => setTab("quiz")}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            background: tab === "quiz" ? "var(--primary)" : "transparent",
            color: tab === "quiz" ? "var(--primary-foreground)" : "var(--foreground)",
            fontWeight: tab === "quiz" ? 600 : 500,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            transition: "all 0.15s ease",
          }}
        >
          <Brain style={{ width: 15, height: 15 }} /> Quiz
        </button>

        <button
          onClick={() => setTab("flashcards")}
          style={{
            padding: "8px 16px",
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            background: tab === "flashcards" ? "var(--primary)" : "transparent",
            color: tab === "flashcards" ? "var(--primary-foreground)" : "var(--foreground)",
            fontWeight: tab === "flashcards" ? 600 : 500,
            fontSize: 13,
            display: "flex",
            alignItems: "center",
            gap: 8,
            fontFamily: "ui-sans-serif,system-ui,sans-serif",
            transition: "all 0.15s ease",
          }}
        >
          <Layers style={{ width: 15, height: 15 }} /> Flashcards
        </button>
      </div>

      {tab === "summary" && <SummaryPanel collectionId={idNum} />}
      {tab === "quiz" && <QuizPanel collectionId={idNum} />}
      {tab === "flashcards" && <FlashcardsPanel collectionId={idNum} />}
    </div>
  )
}

function SummaryPanel({ collectionId }: { collectionId: number }) {
  const [focus, setFocus] = useState("")
  const [length, setLength] = useState<"short" | "medium" | "long">("medium")
  const [result, setResult] = useState<{ summary: string; key_points: string[] } | null>(null)
  const [copied, setCopied] = useState(false)

  const mutation = useGenerateSummary(collectionId)

  const handleGenerate = () => {
    mutation.mutate(
      { focus: focus.trim() || undefined, length },
      { onSuccess: (data) => setResult(data) }
    )
  }

  const handleCopy = () => {
    if (!result) return
    const kp = result.key_points && result.key_points.length ? "Key Points:\n" + result.key_points.map((p) => "- " + p).join("\n") + "\n\n" : ""
    const text = "# Summary\n\n" + kp + result.summary
    navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div>
      <div style={{ background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 14, padding: 22, marginBottom: 24 }}>
        <h3 style={{ fontFamily: "'Georgia',serif", fontSize: 17, fontWeight: 700, margin: "0 0 6px", color: "var(--foreground)" }}>
          Synthesize Notes & Materials
        </h3>
        <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, margin: "0 0 16px" }}>
          Generate a clear synthesis highlighting key concepts, formulas, and takeaways.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, marginBottom: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Focus topic (optional)
            </label>
            <input
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
              placeholder="e.g. key theorems, core definitions, exam topics"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${SB_BORDER}`,
                background: "var(--background)",
                color: "var(--foreground)",
                fontSize: 13,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Length
            </label>
            <select
              value={length}
              onChange={(e) => setLength(e.target.value as any)}
              style={{
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${SB_BORDER}`,
                background: "var(--background)",
                color: "var(--foreground)",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              <option value="short">Short (2-3 paragraphs)</option>
              <option value="medium">Medium (4-5 paragraphs)</option>
              <option value="long">Comprehensive (In-depth)</option>
            </select>
          </div>
        </div>

        <Button onClick={handleGenerate} disabled={mutation.isPending} className="gap-2">
          <Sparkles style={{ width: 14, height: 14 }} />
          {mutation.isPending ? "Generating with local LLM..." : "Generate Summary"}
        </Button>

        {mutation.isError && (
          <p style={{ color: "var(--destructive)", fontSize: 13, marginTop: 10 }}>
            {mutation.error.message}
          </p>
        )}
      </div>

      {result && (
        <div style={{ background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 14, padding: 26 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 18 }}>
            <h3 style={{ fontFamily: "'Georgia',serif", fontSize: 19, fontWeight: 700, margin: 0, color: "var(--foreground)" }}>
              Executive Summary
            </h3>
            <Button variant="ghost" size="sm" onClick={handleCopy} className="gap-2">
              <Copy style={{ width: 14, height: 14 }} />
              {copied ? "Copied!" : "Copy"}
            </Button>
          </div>

          {result.key_points && result.key_points.length > 0 && (
            <div style={{ marginBottom: 20 }}>
              <span style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--primary)" }}>
                Key Points
              </span>
              <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 8 }}>
                {result.key_points.map((pt, i) => (
                  <div key={i} style={{ display: "flex", alignItems: "baseline", gap: 10, fontSize: 13, color: "var(--foreground)" }}>
                    <span style={{ color: "var(--primary)", fontWeight: 700 }}>•</span>
                    <span>{pt}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 14,
              color: "var(--foreground)",
              lineHeight: 1.75,
              whiteSpace: "pre-wrap",
            }}
          >
            {result.summary}
          </div>
        </div>
      )}
    </div>
  )
}

function QuizPanel({ collectionId }: { collectionId: number }) {
  const [topic, setTopic] = useState("")
  const [numQ, setNumQ] = useState(5)
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">("medium")
  const [questions, setQuestions] = useState<QuizQuestion[]>([])
  const [selectedAnswers, setSelectedAnswers] = useState<Record<number, number>>({})
  const [isSubmitted, setIsSubmitted] = useState(false)

  const mutation = useGenerateQuiz(collectionId)

  const handleGenerate = () => {
    mutation.mutate(
      { topic: topic.trim() || undefined, num_questions: numQ, difficulty },
      {
        onSuccess: (data) => {
          setQuestions(data.questions)
          setSelectedAnswers({})
          setIsSubmitted(false)
        },
      }
    )
  }

  const score = questions.reduce((acc, q, idx) => (selectedAnswers[idx] === q.correct_index ? acc + 1 : acc), 0)

  return (
    <div>
      <div style={{ background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 14, padding: 22, marginBottom: 24 }}>
        <h3 style={{ fontFamily: "'Georgia',serif", fontSize: 17, fontWeight: 700, margin: "0 0 6px", color: "var(--foreground)" }}>
          Interactive Assessment Quiz
        </h3>
        <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, margin: "0 0 16px" }}>
          Test your comprehension with questions curated directly from your notes.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr auto", gap: 12, marginBottom: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Topic (optional)
            </label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Chapter 3, Algorithms"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${SB_BORDER}`,
                background: "var(--background)",
                color: "var(--foreground)",
                fontSize: 13,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Difficulty
            </label>
            <select
              value={difficulty}
              onChange={(e) => setDifficulty(e.target.value as any)}
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${SB_BORDER}`,
                background: "var(--background)",
                color: "var(--foreground)",
                fontSize: 13,
                cursor: "pointer",
              }}
            >
              <option value="easy">Easy (Fundamentals)</option>
              <option value="medium">Medium (Standard)</option>
              <option value="hard">Hard (Challenging)</option>
            </select>
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Questions: {numQ}
            </label>
            <input
              type="range"
              min={3}
              max={10}
              value={numQ}
              onChange={(e) => setNumQ(Number(e.target.value))}
              style={{ width: 120, accentColor: "var(--primary)", marginTop: 10 }}
            />
          </div>
        </div>

        <Button onClick={handleGenerate} disabled={mutation.isPending} className="gap-2">
          <Brain style={{ width: 14, height: 14 }} />
          {mutation.isPending ? "Generating Questions..." : "Create Quiz"}
        </Button>

        {mutation.isError && (
          <p style={{ color: "var(--destructive)", fontSize: 13, marginTop: 10 }}>
            {mutation.error.message}
          </p>
        )}
      </div>

      {questions.length > 0 && (
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {isSubmitted && (
            <div
              style={{
                background: "var(--card)",
                border: `1px solid ${SB_BORDER}`,
                borderRadius: 14,
                padding: 20,
                textAlign: "center",
              }}
            >
              <div style={{ fontSize: 32, marginBottom: 6 }}>{score === questions.length ? "🎉" : score >= questions.length / 2 ? "👏" : "📖"}</div>
              <h2 style={{ fontFamily: "'Georgia',serif", fontSize: 20, fontWeight: 700, margin: 0, color: "var(--foreground)" }}>
                Your Score: {score} / {questions.length} ({Math.round((score / questions.length) * 100)}%)
              </h2>
              <p style={{ fontSize: 13, color: SB_MUTED, marginTop: 4 }}>
                {score === questions.length ? "Flawless! Excellent mastery." : score >= questions.length / 2 ? "Solid knowledge! Review the explanations below." : "Review your notes and try again."}
              </p>
            </div>
          )}

          {questions.map((q, qIdx) => {
            const userChoice = selectedAnswers[qIdx]

            return (
              <div
                key={qIdx}
                style={{
                  background: "var(--card)",
                  border: `1px solid ${SB_BORDER}`,
                  borderRadius: 14,
                  padding: 20,
                }}
              >
                <div style={{ fontSize: 14, fontWeight: 600, color: "var(--foreground)", marginBottom: 12 }}>
                  {qIdx + 1}. {q.question}
                </div>

                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {q.options.map((opt, optIdx) => {
                    const isSelected = userChoice === optIdx
                    const isCorrect = isSubmitted && optIdx === q.correct_index
                    const isWrong = isSubmitted && isSelected && !isCorrect

                    let bg = "var(--background)"
                    let borderColor = SB_BORDER
                    let textColor = "var(--foreground)"

                    if (isSubmitted) {
                      if (isCorrect) {
                        bg = "rgba(46, 204, 113, 0.15)"
                        borderColor = "#2ecc71"
                      } else if (isWrong) {
                        bg = "rgba(231, 76, 60, 0.15)"
                        borderColor = "#e74c3c"
                      }
                    } else if (isSelected) {
                      bg = "var(--accent)"
                      borderColor = "var(--primary)"
                    }

                    return (
                      <div
                        key={optIdx}
                        onClick={() => {
                          if (!isSubmitted) {
                            setSelectedAnswers((prev) => ({ ...prev, [qIdx]: optIdx }))
                          }
                        }}
                        style={{
                          padding: "10px 14px",
                          borderRadius: 8,
                          border: `1px solid ${borderColor}`,
                          background: bg,
                          color: textColor,
                          fontSize: 13,
                          cursor: isSubmitted ? "default" : "pointer",
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                          transition: "all 0.1s ease",
                        }}
                      >
                        <span style={{ fontWeight: 700, width: 20 }}>{String.fromCharCode(65 + optIdx)}.</span>
                        <span style={{ flex: 1 }}>{opt}</span>
                        {isSubmitted && isCorrect && <CheckCircle2 style={{ width: 16, height: 16, color: "#2ecc71" }} />}
                        {isSubmitted && isWrong && <XCircle style={{ width: 16, height: 16, color: "#e74c3c" }} />}
                      </div>
                    )
                  })}
                </div>

                {isSubmitted && q.explanation && (
                  <div
                    style={{
                      marginTop: 12,
                      padding: "8px 12px",
                      borderRadius: 8,
                      background: "var(--muted)",
                      fontSize: 12,
                      color: SB_MUTED,
                      display: "flex",
                      alignItems: "baseline",
                      gap: 6,
                    }}
                  >
                    <HelpCircle style={{ width: 13, height: 13, flexShrink: 0 }} />
                    <span>{q.explanation}</span>
                  </div>
                )}
              </div>
            )
          })}

          <div style={{ display: "flex", justifyContent: "flex-end", gap: 12, marginTop: 8 }}>
            {!isSubmitted ? (
              <Button
                onClick={() => setIsSubmitted(true)}
                disabled={Object.keys(selectedAnswers).length < questions.length}
              >
                Submit Answers
              </Button>
            ) : (
              <Button variant="outline" onClick={handleGenerate} className="gap-2">
                <RotateCw style={{ width: 14, height: 14 }} /> Try Another Quiz
              </Button>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

function FlashcardsPanel({ collectionId }: { collectionId: number }) {
  const [topic, setTopic] = useState("")
  const [numCards, setNumCards] = useState(8)
  const [cards, setCards] = useState<{ front: string; back: string; tags: string[] }[]>([])
  const [currentIdx, setCurrentIdx] = useState(0)
  const [isFlipped, setIsFlipped] = useState(false)

  const mutation = useGenerateFlashcards(collectionId)

  const handleGenerate = () => {
    mutation.mutate(
      { topic: topic.trim() || undefined, num_cards: numCards },
      {
        onSuccess: (data) => {
          setCards(data.cards)
          setCurrentIdx(0)
          setIsFlipped(false)
        },
      }
    )
  }

  const current = cards[currentIdx]

  return (
    <div>
      <div style={{ background: "var(--card)", border: `1px solid ${SB_BORDER}`, borderRadius: 14, padding: 22, marginBottom: 24 }}>
        <h3 style={{ fontFamily: "'Georgia',serif", fontSize: 17, fontWeight: 700, margin: "0 0 6px", color: "var(--foreground)" }}>
          Active Recall Deck
        </h3>
        <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, margin: "0 0 16px" }}>
          Spaced-repetition flashcards generated from definitions, formulas, and theorems.
        </p>

        <div style={{ display: "grid", gridTemplateColumns: "1fr auto", gap: 12, marginBottom: 16 }}>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Topic focus (optional)
            </label>
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Vocabulary, Algorithms, Formulas"
              style={{
                width: "100%",
                padding: "8px 12px",
                borderRadius: 8,
                border: `1px solid ${SB_BORDER}`,
                background: "var(--background)",
                color: "var(--foreground)",
                fontSize: 13,
                outline: "none",
                boxSizing: "border-box",
              }}
            />
          </div>
          <div>
            <label style={{ display: "block", fontSize: 12, fontWeight: 600, color: SB_MUTED, marginBottom: 6 }}>
              Cards: {numCards}
            </label>
            <input
              type="range"
              min={5}
              max={15}
              value={numCards}
              onChange={(e) => setNumCards(Number(e.target.value))}
              style={{ width: 120, accentColor: "var(--primary)", marginTop: 10 }}
            />
          </div>
        </div>

        <Button onClick={handleGenerate} disabled={mutation.isPending} className="gap-2">
          <Layers style={{ width: 14, height: 14 }} />
          {mutation.isPending ? "Generating Deck..." : "Generate Flashcards"}
        </Button>

        {mutation.isError && (
          <p style={{ color: "var(--destructive)", fontSize: 13, marginTop: 10 }}>
            {mutation.error.message}
          </p>
        )}
      </div>

      {cards.length > 0 && current && (
        <div style={{ maxWidth: 600, margin: "0 auto" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 12 }}>
            <span style={{ fontSize: 12, color: SB_MUTED }}>
              Card {currentIdx + 1} of {cards.length}
            </span>
            <span style={{ fontSize: 12, color: "var(--primary)", fontWeight: 600 }}>
              Click card to flip
            </span>
          </div>

          <div style={{ height: 4, width: "100%", background: "var(--muted)", borderRadius: 2, marginBottom: 20, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${((currentIdx + 1) / cards.length) * 100}%`,
                background: "var(--primary)",
                transition: "width 0.2s ease",
              }}
            />
          </div>

          <div
            onClick={() => setIsFlipped(!isFlipped)}
            style={{
              minHeight: 240,
              background: "var(--card)",
              border: `1px solid ${SB_BORDER}`,
              borderRadius: 16,
              padding: 32,
              cursor: "pointer",
              display: "flex",
              flexDirection: "column",
              justifyContent: "center",
              alignItems: "center",
              textAlign: "center",
              boxShadow: "0 6px 24px rgba(0,0,0,0.06)",
              transition: "transform 0.15s ease",
              position: "relative",
            }}
          >
            <div
              style={{
                position: "absolute",
                top: 16,
                left: 20,
                fontSize: 10,
                fontWeight: 700,
                letterSpacing: "0.1em",
                textTransform: "uppercase",
                color: isFlipped ? "var(--primary)" : SB_MUTED,
              }}
            >
              {isFlipped ? "Answer" : "Question"}
            </div>

            <div
              style={{
                fontFamily: isFlipped ? "ui-sans-serif,system-ui,sans-serif" : "'Georgia',serif",
                fontSize: isFlipped ? 16 : 20,
                fontWeight: isFlipped ? 400 : 700,
                color: "var(--foreground)",
                lineHeight: 1.6,
                maxWidth: 480,
              }}
            >
              {isFlipped ? current.back : current.front}
            </div>

            {current.tags && current.tags.length > 0 && (
              <div style={{ display: "flex", gap: 6, position: "absolute", bottom: 16 }}>
                {current.tags.map((t) => (
                  <span
                    key={t}
                    style={{
                      background: "var(--muted)",
                      borderRadius: 100,
                      padding: "2px 8px",
                      fontSize: 10,
                      color: SB_MUTED,
                    }}
                  >
                    {t}
                  </span>
                ))}
              </div>
            )}
          </div>

          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 20 }}>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setCurrentIdx((prev) => Math.max(0, prev - 1))
                setIsFlipped(false)
              }}
              disabled={currentIdx === 0}
              className="gap-1"
            >
              <ChevronLeft style={{ width: 14, height: 14 }} /> Previous
            </Button>
            <Button
              size="sm"
              onClick={() => {
                setCurrentIdx((prev) => Math.min(cards.length - 1, prev + 1))
                setIsFlipped(false)
              }}
              disabled={currentIdx === cards.length - 1}
              className="gap-1"
            >
              Next <ChevronRight style={{ width: 14, height: 14 }} />
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}