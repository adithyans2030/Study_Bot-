import { zodResolver } from "@hookform/resolvers/zod"
import { Eye, EyeOff, Loader2, Lock } from "lucide-react"
import { useState } from "react"
import { useForm, useWatch } from "react-hook-form"
import { Link, Navigate, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Skeleton } from "@/components/ui/skeleton"
import { ApiError } from "@/lib/api"
import { AuthLayout } from "./AuthLayout"
import { useAuthStatus, useRegister } from "./hooks"
import { passwordStrength, type RegisterInput, registerSchema } from "./schema"

export function RegisterPage() {
  const status = useAuthStatus()
  const registerAccount = useRegister()
  const navigate = useNavigate()
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    control,
    formState: { errors, isSubmitting },
  } = useForm<RegisterInput>({ resolver: zodResolver(registerSchema) })
  const password = useWatch({ control, name: "password", defaultValue: "" })

  if (status.isPending) {
    return (
      <AuthLayout>
        <div className="space-y-4">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-10 w-full" />
          <Skeleton className="h-10 w-full" />
        </div>
      </AuthLayout>
    )
  }

  if (status.data?.user) return <Navigate to="/app" replace />

  // Registration is intentionally closed after the first account (a security decision, not a
  // placeholder — see PLAN.md) — an honest dead end beats a form that submits to a 403.
  if (status.data && !status.data.registration_open) {
    return (
      <AuthLayout>
        <div className="space-y-4 text-center sm:text-left">
          <div className="bg-muted mx-auto flex size-10 items-center justify-center rounded-full sm:mx-0">
            <Lock className="text-muted-foreground size-5" />
          </div>
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold">Registration is closed</h1>
            <p className="text-muted-foreground text-sm">
              This StudyBot already has an owner. Ask them to create your account, or to turn on
              open registration.
            </p>
          </div>
          <Button asChild className="w-full">
            <Link to="/login">Back to sign in</Link>
          </Button>
        </div>
      </AuthLayout>
    )
  }

  const becomingOwner = status.data ? !status.data.has_users : false
  const strength = password ? passwordStrength(password) : null

  const onSubmit = handleSubmit(async (values) => {
    try {
      await registerAccount.mutateAsync(values)
      navigate("/app", { replace: true })
    } catch {
      // Shown below via registerAccount.error.
    }
  })

  return (
    <AuthLayout>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <div className="space-y-2 text-center sm:text-left" style={{ marginBottom: 28 }}>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", color: "#6b6b6b", textTransform: "uppercase", marginBottom: 12 }}>
            {becomingOwner ? "First account" : "New here"}
          </p>
          <h1 style={{ fontFamily: "'Georgia','Times New Roman',serif", fontSize: "clamp(1.8rem,3vw,2.4rem)", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-0.025em", color: "#1a1a1a", marginBottom: 10 }}>
            {becomingOwner ? "Set up your space." : "Start fresh."}
          </h1>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: "#6b6b6b", lineHeight: 1.6 }}>
            {becomingOwner
              ? "You're the first person here — this account owns the server."
              : "Your own private library. Nobody else can see it."}
          </p>
        </div>

        {registerAccount.error && (
          <p
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
          >
            {registerAccount.error instanceof ApiError
              ? registerAccount.error.message
              : "Something went wrong."}
          </p>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            autoComplete="username"
            autoFocus
            aria-invalid={!!errors.username}
            {...register("username")}
          />
          {errors.username && <p className="text-destructive text-sm">{errors.username.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="new-password"
              aria-invalid={!!errors.password}
              className="pr-10"
              {...register("password")}
            />
            <button
              type="button"
              onClick={() => setShowPassword((v) => !v)}
              className="text-muted-foreground hover:text-foreground absolute inset-y-0 right-0 flex w-10 items-center justify-center"
              aria-label={showPassword ? "Hide password" : "Show password"}
            >
              {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
            </button>
          </div>
          {errors.password ? (
            <p className="text-destructive text-sm">{errors.password.message}</p>
          ) : (
            strength && (
              <p className="text-muted-foreground text-sm" aria-live="polite">
                Password strength: {strength.label}
              </p>
            )
          )}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="confirmPassword">Confirm password</Label>
          <Input
            id="confirmPassword"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            aria-invalid={!!errors.confirmPassword}
            {...register("confirmPassword")}
          />
          {errors.confirmPassword && (
            <p className="text-destructive text-sm">{errors.confirmPassword.message}</p>
          )}
        </div>

        <Button
          type="submit"
          className="w-full"
          disabled={isSubmitting || registerAccount.isPending}
        >
          {(isSubmitting || registerAccount.isPending) && <Loader2 className="animate-spin" />}
          {becomingOwner ? "Create the owner account" : "Create account"}
        </Button>

        <p className="text-muted-foreground text-center text-sm">
          Already have an account?{" "}
          <Link to="/login" className="text-primary font-medium hover:underline">
            Sign in
          </Link>
        </p>
      </form>
    </AuthLayout>
  )
}
