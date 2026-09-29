import { Link } from "react-router-dom"

// Fixed brand teal, not a CSS token: this panel is a decorative marketing accent (like the
// landing page), always teal with white text regardless of light/dark mode, not a themed UI
// surface. The form panel to its right is the actual interactive UI and does follow the theme.
const BRAND_GREEN = "#1e4d3f"

/** Split layout: editorial teal panel left (hidden on mobile), cream form panel right.
 *  Mobile-first: single column, panel hidden, form full-width. */
export function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        display: "grid",
        minHeight: "100svh",
        fontFamily: "'Georgia','Times New Roman',serif",
        background: "var(--background)",
      }}
      className="grid-cols-1 lg:grid-cols-2"
    >
      {/* ── Left panel (hidden on mobile, visible lg+) — fixed brand color, not theme-aware ── */}
      <div
        style={{
          background: BRAND_GREEN,
          color: "#fff",
          flexDirection: "column",
          justifyContent: "space-between",
          padding: "40px 48px",
          position: "relative",
          overflow: "hidden",
        }}
        className="hidden lg:flex"
        aria-hidden
      >
        {/* Background decoration */}
        <div
          style={{
            position: "absolute",
            width: 400,
            height: 400,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.04)",
            right: -100,
            top: "50%",
            transform: "translateY(-50%)",
            pointerEvents: "none",
          }}
        />
        <div
          style={{
            position: "absolute",
            width: 250,
            height: 250,
            borderRadius: "50%",
            background: "rgba(255,255,255,0.04)",
            right: 40,
            top: "62%",
            transform: "translateY(-50%)",
            pointerEvents: "none",
          }}
        />

        {/* Logo */}
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div
            style={{
              width: 36,
              height: 36,
              borderRadius: 10,
              background: "rgba(255,255,255,0.15)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontWeight: 700,
              fontSize: 18,
              border: "1px solid rgba(255,255,255,0.2)",
            }}
          >
            S
          </div>
          <span style={{ fontFamily: "'Georgia',serif", fontWeight: 700, fontSize: 20, letterSpacing: "-0.3px" }}>
            StudyBot
          </span>
        </div>

        {/* Tagline */}
        <div style={{ position: "relative", zIndex: 1 }}>
          <p
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 11,
              fontWeight: 600,
              letterSpacing: "0.12em",
              color: "rgba(255,255,255,0.6)",
              marginBottom: 20,
              textTransform: "uppercase",
            }}
          >
            A steadier way to study
          </p>
          <h2
            style={{
              fontFamily: "'Georgia',serif",
              fontSize: "clamp(1.8rem,2.8vw,2.6rem)",
              fontWeight: 700,
              lineHeight: 1.18,
              letterSpacing: "-0.025em",
              color: "#fff",
              marginBottom: 20,
              maxWidth: 340,
            }}
          >
            Make room for the things you're learning.
          </h2>
          <p style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: "rgba(255,255,255,0.7)", lineHeight: 1.65, maxWidth: 320 }}>
            Keep your notes close, find the thread, and let an evidence-based tutor help you practice what matters.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 32 }}>
            <div style={{ width: 7, height: 7, borderRadius: "50%", background: "#7ae0b8" }} />
            <span style={{ fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: "rgba(255,255,255,0.7)" }}>
              Study corner is ready
            </span>
          </div>
        </div>

        {/* Footer */}
        <p style={{ fontFamily: "ui-monospace,monospace", fontSize: 10, color: "rgba(255,255,255,0.4)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
          Notes in. Noise out.
        </p>
      </div>

      {/* ── Right panel — form ── */}
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          background: "var(--background)",
          padding: "0 24px",
        }}
      >
        {/* Top bar */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            padding: "20px 0",
            borderBottom: "1px solid var(--border)",
          }}
        >
          {/* Mobile logo */}
          <Link
            to="/"
            style={{
              alignItems: "center",
              gap: 10,
              textDecoration: "none",
            }}
            className="flex lg:hidden"
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: 8,
                background: "var(--primary)",
                color: "var(--primary-foreground)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontWeight: 700,
                fontSize: 15,
                fontFamily: "'Georgia',serif",
              }}
            >
              S
            </div>
            <span style={{ fontFamily: "'Georgia',serif", fontWeight: 700, fontSize: 17, color: "var(--foreground)" }}>
              StudyBot
            </span>
          </Link>
          <Link
            to="/"
            style={{
              fontFamily: "ui-sans-serif,system-ui,sans-serif",
              fontSize: 13,
              color: "var(--muted-foreground)",
              textDecoration: "none",
              letterSpacing: "0.02em",
            }}
          >
            ← Back to home
          </Link>
        </div>

        {/* Form centred vertically */}
        <div
          style={{
            display: "flex",
            flex: 1,
            alignItems: "center",
            justifyContent: "center",
            padding: "40px 0",
          }}
        >
          <div style={{ width: "100%", maxWidth: 400 }}>{children}</div>
        </div>
      </div>
    </div>
  )
}

