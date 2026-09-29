import { LogOut, User as UserIcon } from "lucide-react"
import { Link, Outlet } from "react-router-dom"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { ThemeToggle } from "@/design-system/ThemeToggle"
import { useAuthStatus, useLogout } from "@/features/auth/hooks"

// CSS custom properties (tokens.css), not fixed hex â€” so this shell follows light/dark like the
// rest of the app instead of staying permanently light.
const SB_GREEN = "var(--primary)"
const SB_CREAM = "var(--background)"

/** Signed-in app shell â€” editorial warm cream nav matching the landing page. */
export function AppShell() {
  const status = useAuthStatus()
  const logout = useLogout()
  const user = status.data?.user
  const initials = user ? user.username.slice(0, 2).toUpperCase() : "?"

  return (
    <div style={{ background: SB_CREAM, minHeight: "100svh", display: "flex", flexDirection: "column" }}>
      {/* â”€â”€ Top bar â”€â”€ */}
      <header
        style={{
          background: "var(--card)",
          borderBottom: "1px solid var(--border)",
          height: 56,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          position: "sticky",
          top: 0,
          zIndex: 50,
        }}
      >
        {/* Brand */}
        <Link
          to="/app"
          style={{ display: "flex", alignItems: "center", gap: 10, textDecoration: "none" }}
          aria-label="Dashboard"
        >
          <div
            style={{
              width: 30,
              height: 30,
              borderRadius: 8,
              background: SB_GREEN,
              color: "var(--primary-foreground)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontFamily: "'Georgia',serif",
              fontWeight: 700,
              fontSize: 14,
              flexShrink: 0,
            }}
          >
            S
          </div>
          <span
            style={{
              fontFamily: "'Georgia',serif",
              fontWeight: 700,
              fontSize: 17,
              color: "var(--foreground)",
              letterSpacing: "-0.2px",
            }}
          >
            StudyBot
          </span>
        </Link>

        {/* Primary nav */}
        <nav style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: 16 }}>
          <Link
            to="/app"
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              color: "var(--foreground)",
              textDecoration: "none",
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
            }}
          >
            Library
          </Link>
          <Link
            to="/app/knowledge"
            style={{
              padding: "6px 12px",
              borderRadius: 6,
              fontSize: 13,
              fontWeight: 500,
              color: "var(--foreground)",
              textDecoration: "none",
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
            }}
          >
            Knowledge Graph
          </Link>
        </nav>

        {/* Right side: status dot + user menu */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
            <div style={{ width: 6, height: 6, borderRadius: "50%", background: "#7ae0b8" }} aria-hidden />
            <span
              style={{
                fontFamily: "ui-sans-serif,system-ui,sans-serif",
                fontSize: 12,
                color: "var(--muted-foreground)",
                letterSpacing: "0.02em",
              }}
              className="hidden sm:inline"
            >
              Your quiet corner for learning
            </span>
          </div>

          <ThemeToggle />

          {user && (
            <DropdownMenu>
              <DropdownMenuTrigger
                style={{
                  width: 34,
                  height: 34,
                  borderRadius: "50%",
                  background: SB_GREEN,
                  color: "var(--primary-foreground)",
                  border: "none",
                  cursor: "pointer",
                  fontFamily: "ui-sans-serif,system-ui,sans-serif",
                  fontWeight: 600,
                  fontSize: 12,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
                aria-label={`Account: ${user.username}`}
              >
                {initials}
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel
                  style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif" }}
                  className="flex items-center gap-2 font-normal"
                >
                  <UserIcon className="text-muted-foreground size-4" />
                  {user.username}
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onSelect={() => logout.mutate()} disabled={logout.isPending}>
                  <LogOut /> Sign out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          )}
        </div>
      </header>

      <main style={{ flex: 1 }}>
        <Outlet />
      </main>
    </div>
  )
}


