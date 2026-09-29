import { Eye, EyeOff, Loader2 } from "lucide-react"
import { useState } from "react"
import { useForm } from "react-hook-form"
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { ApiError } from "@/lib/api"
import { AuthLayout } from "./AuthLayout"
import { useAuthStatus, useLogin } from "./hooks"

interface LoginInput {
  username: string
  password: string
}

// No zod here on purpose: signing in only needs "did you type something", which react-hook-form's
// own `required` rule covers, and this is the most-visited route in the app — every byte of zod +
// the resolver package (pulled in for /register instead, a rare one-time visit) is a byte every
// sign-in pays for otherwise. See the "route-level code splitting" note in router.tsx.
export function LoginPage() {
  const status = useAuthStatus()
  const login = useLogin()
  const navigate = useNavigate()
  const location = useLocation()
  const [showPassword, setShowPassword] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginInput>()

  if (status.data?.user) {
    const from = (location.state as { from?: string } | null)?.from ?? "/app"
    return <Navigate to={from} replace />
  }

  const onSubmit = handleSubmit(async (values) => {
    try {
      await login.mutateAsync(values)
      const from = (location.state as { from?: string } | null)?.from ?? "/app"
      navigate(from, { replace: true })
    } catch {
      // Shown below via login.error; nothing else to do.
    }
  })

  return (
    <AuthLayout>
      <form onSubmit={onSubmit} noValidate className="space-y-5">
        <div className="space-y-2 text-center sm:text-left" style={{ marginBottom: 28 }}>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", color: "#6b6b6b", textTransform: "uppercase", marginBottom: 12 }}>
            Welcome back
          </p>
          <h1 style={{ fontFamily: "'Georgia','Times New Roman',serif", fontSize: "clamp(1.8rem,3vw,2.4rem)", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-0.025em", color: "#1a1a1a", marginBottom: 10 }}>
            Pick up your thread.
          </h1>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: "#6b6b6b", lineHeight: 1.6 }}>
            Sign in to return to your subjects and keep the momentum going.
          </p>
        </div>

        {login.error && (
          <p
            role="alert"
            className="bg-destructive/10 text-destructive rounded-md px-3 py-2 text-sm"
          >
            {login.error instanceof ApiError
              ? loginErrorMessage(login.error)
              : "Something went wrong. Try again."}
          </p>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="username">Username</Label>
          <Input
            id="username"
            autoComplete="username"
            autoFocus
            aria-invalid={!!errors.username}
            {...register("username", { required: "Enter your username." })}
          />
          {errors.username && <p className="text-destructive text-sm">{errors.username.message}</p>}
        </div>

        <div className="space-y-1.5">
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              aria-invalid={!!errors.password}
              className="pr-10"
              {...register("password", { required: "Enter your password." })}
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
          {errors.password && <p className="text-destructive text-sm">{errors.password.message}</p>}
        </div>

        <Button type="submit" className="w-full" disabled={isSubmitting || login.isPending}>
          {(isSubmitting || login.isPending) && <Loader2 className="animate-spin" />}
          Sign in
        </Button>

        {status.data?.registration_open && (
          <p className="text-muted-foreground text-center text-sm">
            First time here?{" "}
            <Link to="/register" className="text-primary font-medium hover:underline">
              Create an account
            </Link>
          </p>
        )}
      </form>
    </AuthLayout>
  )
}

function loginErrorMessage(error: ApiError): string {
  if (error.status === 429) {
    const wait = error.retryAfterSeconds
    return wait ? `${error.message} (about ${Math.ceil(wait / 60)} min)` : error.message
  }
  return error.message
}
