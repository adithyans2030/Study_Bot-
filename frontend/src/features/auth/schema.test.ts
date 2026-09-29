import { describe, expect, it } from "vitest"
import { passwordStrength, registerSchema } from "./schema"

describe("registerSchema", () => {
  const valid = { username: "alice", password: "correcthorse", confirmPassword: "correcthorse" }

  it("accepts a well-formed registration", () => {
    expect(registerSchema.safeParse(valid).success).toBe(true)
  })

  it.each([
    ["Al", "must start with a letter or number and be long enough"], // starts uppercase, too short
    ["ab", "too short (below the server's 3-char minimum)"],
    ["has space", "spaces aren't allowed"],
    ["-leading-dash", "must start with a letter or number, not punctuation"],
  ])("rejects username %j (%s)", (username) => {
    const result = registerSchema.safeParse({ ...valid, username })
    expect(result.success).toBe(false)
  })

  it("accepts the server's own boundary cases (3 and 32 characters)", () => {
    expect(registerSchema.safeParse({ ...valid, username: "abc" }).success).toBe(true)
    expect(registerSchema.safeParse({ ...valid, username: "a".repeat(32) }).success).toBe(true)
    expect(registerSchema.safeParse({ ...valid, username: "a".repeat(33) }).success).toBe(false)
  })

  it("rejects a password under the server's 8-character minimum", () => {
    const result = registerSchema.safeParse({
      ...valid,
      password: "short1",
      confirmPassword: "short1",
    })
    expect(result.success).toBe(false)
  })

  it("rejects mismatched passwords, attributed to confirmPassword", () => {
    const result = registerSchema.safeParse({ ...valid, confirmPassword: "somethingElse123" })
    expect(result.success).toBe(false)
    if (!result.success) {
      expect(result.error.issues[0].path).toEqual(["confirmPassword"])
    }
  })
})

describe("passwordStrength", () => {
  it("flags anything under 8 characters as too short, regardless of variety", () => {
    expect(passwordStrength("aB3!").score).toBe(0)
  })

  it("scores a longer password with no variety as merely okay", () => {
    expect(passwordStrength("aaaaaaaaaa").score).toBe(1)
  })

  it("scores length + variety as good, and a long, varied password as strong", () => {
    expect(passwordStrength("abcdefgh12").score).toBe(2)
    expect(passwordStrength("Correct-Horse-9").score).toBe(3)
  })
})
