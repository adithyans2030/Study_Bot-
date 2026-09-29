import { act, renderHook, waitFor } from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"
import { useChatStream } from "./useChatStream"

function sseResponse(frames: string[], status = 200) {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const frame of frames) controller.enqueue(encoder.encode(frame))
      controller.close()
    },
  })
  return {
    ok: status >= 200 && status < 300,
    status,
    body: stream,
    json: () => Promise.resolve(null),
  } as Response
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("useChatStream", () => {
  it("walks through conversation -> query -> sources -> token* -> done", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: conversation\ndata: {"id":7,"title":"Sobel vs Laplacian"}\n\n',
            'event: query\ndata: {"text":"standalone question"}\n\n',
            'event: sources\ndata: [{"n":1,"title":"Unit 2","type":"pdf","location":"p.3","url":null,"header":"h","snippet":"s"}]\n\n',
            'event: token\ndata: {"text":"Sobel "}\n\n',
            'event: token\ndata: {"text":"detects edges [1]."}\n\n',
            'event: done\ndata: {"text":"Sobel detects edges [1].","cited":[1],"invalid_citations":0,"refused":false,"gated":false,"empty":false,"seconds":2.1,"first_token_seconds":0.5}\n\n',
          ]),
        ),
    )

    const onConversation = vi.fn()
    const onDone = vi.fn()
    const { result } = renderHook(() => useChatStream())

    await act(async () => {
      await result.current.send("What does Sobel do?", {}, onConversation, onDone)
    })

    expect(onConversation).toHaveBeenCalledWith({ id: 7, title: "Sobel vs Laplacian" })
    expect(result.current.liveUser).toBe("What does Sobel do?")
    expect(result.current.liveAnswer.searchQuery).toBe("standalone question")
    expect(result.current.liveAnswer.text).toBe("Sobel detects edges [1].")
    expect(result.current.liveAnswer.sources).toHaveLength(1)
    expect(result.current.liveAnswer.done).toBe(true)
    expect(result.current.sending).toBe(false)
    expect(onDone).toHaveBeenCalledTimes(1)
    expect(onDone.mock.calls[0][0]).toMatchObject({ cited: [1], refused: false })
  })

  it("surfaces a mid-stream error event without throwing", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: conversation\ndata: {"id":1,"title":"x"}\n\n',
            'event: error\ndata: {"message":"The model is unavailable."}\n\n',
          ]),
        ),
    )
    const { result } = renderHook(() => useChatStream())

    await act(async () => {
      await result.current.send("anything", {})
    })

    expect(result.current.liveAnswer.error).toBe("The model is unavailable.")
    expect(result.current.liveAnswer.done).toBe(true)
  })

  it("surfaces an HTTP-level failure (e.g. an unknown collection) as an error state", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        status: 404,
        body: null,
        json: () => Promise.resolve({ detail: "No collection named nonexistent." }),
      }),
    )
    const { result } = renderHook(() => useChatStream())

    await act(async () => {
      await result.current.send("anything", { collections: ["nonexistent"] })
    })

    expect(result.current.liveAnswer.error).toBe("No collection named nonexistent.")
  })

  it("stop() aborts without setting an error", async () => {
    let resolveFetch!: (r: Response) => void
    vi.stubGlobal(
      "fetch",
      vi.fn(
        () =>
          new Promise<Response>((resolve) => {
            resolveFetch = resolve
          }),
      ),
    )
    const { result } = renderHook(() => useChatStream())

    let sendPromise!: Promise<void>
    act(() => {
      sendPromise = result.current.send("anything", {})
    })
    act(() => result.current.stop())
    resolveFetch(sseResponse([]))
    await act(async () => {
      await sendPromise
    })

    expect(result.current.liveAnswer.error).toBeNull()
    await waitFor(() => expect(result.current.sending).toBe(false))
  })

  it("clear() resets to the empty state", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          sseResponse([
            'event: done\ndata: {"text":"hi","cited":[],"invalid_citations":0,"refused":false,"gated":false,"empty":false,"seconds":1,"first_token_seconds":1}\n\n',
          ]),
        ),
    )
    const { result } = renderHook(() => useChatStream())
    await act(async () => {
      await result.current.send("q", {})
    })
    act(() => result.current.clear())

    expect(result.current.liveUser).toBeNull()
    expect(result.current.liveAnswer.text).toBe("")
  })
})
