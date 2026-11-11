import { useMutation } from "@tanstack/react-query"

export interface SummaryRequest {
  document_id?: number
  focus?: string
  length?: "short" | "medium" | "long"
}

export interface SummaryResponse {
  summary: string
  key_points: string[]
}

export interface QuizRequest {
  document_id?: number
  topic?: string
  num_questions?: number
  difficulty?: "easy" | "medium" | "hard"
}

export interface SourceRef {
  n: number
  node_id: number
  title: string
  type: string
  source_document: string
}

export interface QuizQuestion {
  question: string
  options: string[]
  correct_index: number
  explanation: string
  source?: SourceRef | null
}

export interface QuizResponse {
  questions: QuizQuestion[]
}

export interface FlashcardRequest {
  document_id?: number
  topic?: string
  num_cards?: number
}

export interface Flashcard {
  front: string
  back: string
  tags: string[]
  source?: SourceRef | null
}

export interface FlashcardsResponse {
  cards: Flashcard[]
}

export interface QuizAttemptItem {
  node_id?: number | null
  correct: boolean
}

export interface QuizAttemptsResponse {
  recorded: number
}

export interface PlanNode {
  node_id: number
  title: string
  type: string
  source_document: string
  status: "untested" | "weak" | "known"
  accuracy?: number | null
  last_attempt_at?: number | null
}

export interface PlanDay {
  date: string
  day_index: number
  nodes: PlanNode[]
}

export interface StudyPlanResponse {
  deadline: string
  days_remaining: number
  days: PlanDay[]
}

export async function generateSummary(collectionId: number, req: SummaryRequest): Promise<SummaryResponse> {
  const res = await fetch(`/api/collections/${collectionId}/study/summarize`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || "Failed to generate summary")
  }
  return res.json()
}

export async function generateQuiz(collectionId: number, req: QuizRequest): Promise<QuizResponse> {
  const res = await fetch(`/api/collections/${collectionId}/study/quiz`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || "Failed to generate quiz")
  }
  return res.json()
}

export async function generateFlashcards(collectionId: number, req: FlashcardRequest): Promise<FlashcardsResponse> {
  const res = await fetch(`/api/collections/${collectionId}/study/flashcards`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || "Failed to generate flashcards")
  }
  return res.json()
}

export async function recordQuizAttempts(collectionId: number, attempts: QuizAttemptItem[]): Promise<QuizAttemptsResponse> {
  const res = await fetch(`/api/collections/${collectionId}/study/quiz/attempts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ attempts }),
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || "Failed to record quiz attempts")
  }
  return res.json()
}

export async function generatePlan(collectionId: number, deadline: string): Promise<StudyPlanResponse> {
  const res = await fetch(`/api/collections/${collectionId}/study/plan?deadline=${encodeURIComponent(deadline)}`)
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || "Failed to generate study plan")
  }
  return res.json()
}

export function useGenerateSummary(collectionId: number) {
  return useMutation({
    mutationFn: (req: SummaryRequest) => generateSummary(collectionId, req),
  })
}

export function useGenerateQuiz(collectionId: number) {
  return useMutation({
    mutationFn: (req: QuizRequest) => generateQuiz(collectionId, req),
  })
}

export function useGenerateFlashcards(collectionId: number) {
  return useMutation({
    mutationFn: (req: FlashcardRequest) => generateFlashcards(collectionId, req),
  })
}

export function useRecordQuizAttempts(collectionId: number) {
  return useMutation({
    mutationFn: (attempts: QuizAttemptItem[]) => recordQuizAttempts(collectionId, attempts),
  })
}

export function useGeneratePlan(collectionId: number) {
  return useMutation({
    mutationFn: (deadline: string) => generatePlan(collectionId, deadline),
  })
}
