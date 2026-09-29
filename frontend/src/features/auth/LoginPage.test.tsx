import { screen, waitFor } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, describe, expect, it, vi } from "vitest"
import { renderWithProviders } from "@/test/render"
import { LoginPage } from "./LoginPage"

/** Routes a mocked fetch by URL, the way the real backend would answer each endpoint —
 * LoginPage calls both /api/auth/status (on mount) and /api/auth/login (on submit). */
function mockBackend(handlers: Record<string, { status: number; body?: unknown }>) {
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string) => {
      const path = url.replace(/^https?:\/\/[^/]+/, "")
      const response = handlers[path]
      if (!response) throw new Error(`Unmocked request: ${path}`)
      return Promise.resolve({
        ok: response.status >= 200 && response.status < 300,
        status: response.status,
        headers: new Headers(),
        json: () => Promise.resolve(response.body),
      })
    }),
  )
}

const OPEN_STATUS = { status: 200, body: { has_users: true, registration_open: false, user: null } }

afterEach(() => {
  vi.unstubAllGlobals()
})

describe("LoginPage", () => {
  it("rejects an empty submission without calling the server", async () => {
    mockBackend({ "/api/auth/status": OPEN_STATUS })
    renderWithProviders(<LoginPage />)
    await userEvent.click(await screen.findByRole("button", { name: "Sign in" }))

    expect(await screen.findByText("Enter your username.")).toBeInTheDocument()
    expect(screen.getByText("Enter your password.")).toBeInTheDocument()
    expect(vi.mocked(fetch)).toHaveBeenCalledTimes(1) // only the status check, never /login
  })

  it("shows the server's error message on a failed sign-in", async () => {
    mockBackend({
      "/api/auth/status": OPEN_STATUS,
      "/api/auth/login": { status: 401, body: { detail: "Wrong username or password." } },
    })
    renderWithProviders(<LoginPage />)

    await userEvent.type(screen.getByLabelText("Username"), "alice")
    await userEvent.type(screen.getByLabelText("Password"), "wrong-password")
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("Wrong username or password.")
  })

  it("submits the typed credentials to /api/auth/login", async () => {
    mockBackend({
      "/api/auth/status": OPEN_STATUS,
      "/api/auth/login": { status: 200, body: { id: 1, username: "alice", is_admin: true } },
    })
    renderWithProviders(<LoginPage />)

    await userEvent.type(screen.getByLabelText("Username"), "alice")
    await userEvent.type(screen.getByLabelText("Password"), "correcthorse")
    await userEvent.click(screen.getByRole("button", { name: "Sign in" }))

    await waitFor(() => {
      const loginCall = vi
        .mocked(fetch)
        .mock.calls.find(([url]) => (url as string).includes("/api/auth/login"))
      expect(loginCall?.[1]?.body).toBe(
        JSON.stringify({ username: "alice", password: "correcthorse" }),
      )
    })
  })

  it("toggles the password field between hidden and visible", async () => {
    mockBackend({ "/api/auth/status": OPEN_STATUS })
    renderWithProviders(<LoginPage />)

    const password = screen.getByLabelText("Password")
    expect(password).toHaveAttribute("type", "password")
    await userEvent.click(screen.getByRole("button", { name: "Show password" }))
    expect(password).toHaveAttribute("type", "text")
  })
})
