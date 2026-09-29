import { z } from "zod"

// Mirrors app/core/accounts.py exactly, so a mistake is caught before the round trip rather than
// after — the server remains the real authority and re-checks everything itself regardless.
const USERNAME = /^[a-z0-9][a-z0-9_.-]{2,31}$/

export const usernameField = z
  .string()
  .trim()
  .min(1, "Enter a username.")
  .regex(
    USERNAME,
    "3-32 characters: lowercase letters, numbers, dot, dash or underscore, starting with a letter or number.",
  )

export const credentialsSchema = z.object({
  username: usernameField,
  password: z.string().min(8, "At least 8 characters.").max(128, "At most 128 characters."),
})

export type CredentialsInput = z.infer<typeof credentialsSchema>

// Login has no schema here at all — see the comment at the top of LoginPage.tsx: it only needs
// "did you type something", which react-hook-form's own `required` rule covers with no zod import.

export const registerSchema = credentialsSchema
  .extend({ confirmPassword: z.string() })
  .refine((v) => v.password === v.confirmPassword, {
    message: "Passwords don't match.",
    path: ["confirmPassword"],
  })

export type RegisterInput = z.infer<typeof registerSchema>

/** A quick, local, no-dependency hint — not a security gate (the server enforces the real
 * minimum). Long enough to skip a ~800 KB zxcvbn-style library for a "nice to have". */
export function passwordStrength(password: string): { label: string; score: 0 | 1 | 2 | 3 } {
  if (password.length < 8) return { label: "Too short", score: 0 }
  const varietyPoints = [/[a-z]/, /[A-Z]/, /[0-9]/, /[^a-zA-Z0-9]/].filter((re) =>
    re.test(password),
  ).length
  const long = password.length >= 12
  if (long && varietyPoints >= 3) return { label: "Strong", score: 3 }
  if (password.length >= 10 && varietyPoints >= 2) return { label: "Good", score: 2 }
  return { label: "Okay", score: 1 }
}
