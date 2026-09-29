import { useEffect, useRef, useState } from "react"
import { Link, Navigate } from "react-router-dom"
import { useAuthStatus } from "@/features/auth/hooks"

/* ─── tiny motion hook ─────────────────────────────── */
function useInView(threshold = 0.15) {
  const ref = useRef<HTMLDivElement>(null)
  const [visible, setVisible] = useState(false)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) setVisible(true) },
      { threshold },
    )
    obs.observe(el)
    return () => obs.disconnect()
  }, [threshold])
  return { ref, visible }
}

/* ─── animated counter ────────────────────────────── */
function Counter({ to, suffix = "" }: { to: number; suffix?: string }) {
  const { ref, visible } = useInView()
  const [val, setVal] = useState(0)
  useEffect(() => {
    if (!visible) return
    let start = 0
    const step = to / 40
    const id = setInterval(() => {
      start += step
      if (start >= to) { setVal(to); clearInterval(id) }
      else setVal(Math.floor(start))
    }, 30)
    return () => clearInterval(id)
  }, [visible, to])
  return <span ref={ref}>{val}{suffix}</span>
}

/* ─── component ───────────────────────────────────── */
export function LandingPage() {
  // Marketing page is for signed-out visitors only — a signed-in user landing on "/" (a bookmark,
  // or the installed PWA's start_url) goes straight to their dashboard instead, same guard LoginPage
  // and RegisterPage already use.
  const status = useAuthStatus()
  const [scrolled, setScrolled] = useState(false)

  useEffect(() => {
    const handler = () => setScrolled(window.scrollY > 20)
    window.addEventListener("scroll", handler, { passive: true })
    return () => window.removeEventListener("scroll", handler)
  }, [])

  const hero = useInView(0.1)
  const feat = useInView(0.1)
  const how  = useInView(0.1)
  const stat = useInView(0.1)
  const cta  = useInView(0.1)

  if (status.data?.user) return <Navigate to="/app" replace />

  return (
    <div style={styles.page}>
      {/* ── NAV ─────────────────────────────────────── */}
      <header style={{ ...styles.nav, ...(scrolled ? styles.navScrolled : {}) }}>
        <div style={styles.navInner}>
          <div style={styles.logo}>
            <span style={styles.logoMark}>S</span>
            <span style={styles.logoText}>StudyBot</span>
          </div>
          <nav style={styles.navLinks}>
            <a href="#features" style={styles.navLink}>Features</a>
            <a href="#how-it-works" style={styles.navLink}>How it works</a>
            <a href="#privacy" style={styles.navLink}>Privacy</a>
          </nav>
          <div style={styles.navActions}>
            <Link to="/login" style={styles.btnGhost}>Sign in</Link>
            <Link to="/register" style={styles.btnPrimary}>Get started free →</Link>
          </div>
        </div>
      </header>

      {/* ── HERO ────────────────────────────────────── */}
      <section style={styles.hero}>
        <div style={styles.heroBgCircle1} aria-hidden />
        <div style={styles.heroBgCircle2} aria-hidden />
        <div ref={hero.ref} style={{ ...styles.heroInner, ...(hero.visible ? styles.fadeIn : styles.fadeOut) }}>
          <div style={styles.heroLeft}>
            <p style={styles.eyebrow}><span style={styles.eyebrowDot} />YOUR PERSONAL STUDY WORKSPACE</p>
            <h1 style={styles.heroHeading}>Ask your notes.<br /><em style={styles.heroHeadingItalic}>Get the answer.</em></h1>
            <p style={styles.heroSub}>StudyBot turns your PDFs, slides, and lecture recordings into a source-grounded tutor that never guesses — only answers from what you gave it, with exact page citations.</p>
            <div style={styles.heroCtas}>
              <Link to="/register" style={styles.btnHeroPrimary}>Create your study space →</Link>
              <Link to="/login" style={styles.btnHeroGhost}>I already have one</Link>
            </div>
            <p style={styles.heroHint}>Free · Runs on your PC · Nothing leaves it</p>
          </div>
          <div style={styles.heroRight} aria-hidden><MockupCard /></div>
        </div>
      </section>

      {/* ── TRUST BAR ───────────────────────────────── */}
      <section style={styles.trustBar}>
        <p style={styles.trustLabel}>Works with your materials</p>
        <div style={styles.trustIcons}>
          {["PDF", "PPTX", "DOCX", "YouTube", "Voice"].map((f) => (
            <span key={f} style={styles.trustChip}>{f}</span>
          ))}
        </div>
      </section>

      {/* ── FEATURES ────────────────────────────────── */}
      <section id="features" style={styles.section}>
        <div ref={feat.ref} style={{ ...styles.sectionInner, ...(feat.visible ? styles.fadeIn : styles.fadeOut) }}>
          <p style={styles.sectionEyebrow}>WHAT STUDYBOT DOES</p>
          <h2 style={styles.sectionHeading}>Make room for the things<br />you are learning.</h2>
          <p style={styles.sectionSub}>Keep your notes close, find the thread, and let an evidence-based tutor help you practice what matters.</p>
          <div style={styles.featureGrid}>
            {features.map((f, i) => <FeatureCard key={i} {...f} delay={i * 80} visible={feat.visible} />)}
          </div>
        </div>
      </section>

      {/* ── HOW IT WORKS ────────────────────────────── */}
      <section id="how-it-works" style={styles.sectionAlt}>
        <div ref={how.ref} style={{ ...styles.sectionInner, ...(how.visible ? styles.fadeIn : styles.fadeOut) }}>
          <p style={styles.sectionEyebrow}>THE METHOD</p>
          <h2 style={styles.sectionHeading}>Three steps to clarity.</h2>
          <div style={styles.stepsGrid}>
            {steps.map((s, i) => <StepCard key={i} {...s} num={i + 1} delay={i * 120} visible={how.visible} />)}
          </div>
        </div>
      </section>

      {/* ── STATS ───────────────────────────────────── */}
      <section id="privacy" style={styles.statSection}>
        <div style={styles.statBg} aria-hidden />
        <div ref={stat.ref} style={{ ...styles.sectionInner, position: "relative", zIndex: 1 }}>
          <p style={{ ...styles.sectionEyebrow, color: "rgba(255,255,255,0.6)" }}>BY THE NUMBERS</p>
          <h2 style={{ ...styles.sectionHeading, color: "#fff" }}>Built for focus,<br />not hype.</h2>
          <div style={styles.statsGrid}>
            {stats.map((s, i) => (
              <div key={i} style={{ ...styles.statCard, opacity: stat.visible ? 1 : 0, transform: stat.visible ? "translateY(0)" : "translateY(24px)", transition: `opacity 0.6s ease ${i * 120}ms, transform 0.6s ease ${i * 120}ms` }}>
                <div style={styles.statNum}><Counter to={s.value} suffix={s.suffix} /></div>
                <div style={styles.statLabel}>{s.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ── CTA ─────────────────────────────────────── */}
      <section style={styles.ctaSection}>
        <div ref={cta.ref} style={{ ...styles.ctaInner, ...(cta.visible ? styles.fadeIn : styles.fadeOut) }}>
          <p style={styles.sectionEyebrow}>START TODAY</p>
          <h2 style={{ ...styles.sectionHeading, maxWidth: 560 }}>Your notes deserve better questions.</h2>
          <p style={{ ...styles.sectionSub, marginBottom: 40 }}>Upload your first PDF and ask it something. StudyBot answers from the source — every time, with a page number.</p>
          <div style={styles.heroCtas}>
            <Link to="/register" style={styles.btnHeroPrimary}>Create your study space →</Link>
            <Link to="/login" style={styles.btnHeroGhost}>Sign in</Link>
          </div>
        </div>
      </section>

      {/* ── FOOTER ──────────────────────────────────── */}
      <footer style={styles.footer}>
        <div style={styles.footerInner}>
          <div style={styles.logo}>
            <span style={styles.logoMark}>S</span>
            <span style={{ ...styles.logoText, color: "#6b6b6b" }}>StudyBot</span>
          </div>
          <p style={styles.footerNote}>Free · Local-first · Open source · Nothing leaves your PC</p>
        </div>
      </footer>
    </div>
  )
}

function MockupCard() {
  const [active, setActive] = useState(0)
  const cards = [
    { tag: "a question worth keeping", q: "What do I understand well enough to explain?", hint: "Small, honest prompts for the spaces between rereading." },
    { tag: "from your notes", q: "How does RANSAC reject outliers?", hint: "Cited answer from Computer_Vision_Unit_2.pdf · p. 34" },
    { tag: "voice mode", q: "Can I ask this out loud?", hint: "Press mic, speak, pause. Transcribed offline on your PC." },
  ]
  useEffect(() => {
    const id = setInterval(() => setActive((a) => (a + 1) % cards.length), 3200)
    return () => clearInterval(id)
  }, [cards.length])
  const c = cards[active]
  return (
    <div style={styles.mockupWrapper}>
      <div style={styles.mockupCard}>
        <div style={styles.mockupHeader}>
          <span style={styles.mockupLabel}>TODAY{String.fromCharCode(39)}S DESK</span>
          <span style={styles.mockupCounter}>{String(active + 1).padStart(2, "0")} / {String(cards.length).padStart(2, "0")}</span>
        </div>
        <p style={styles.mockupTag}># {c.tag}</p>
        <h3 style={styles.mockupQ}>{c.q}</h3>
        <p style={styles.mockupHint}>{c.hint}</p>
        <div style={styles.mockupFooter}>
          <span style={styles.mockupCta}>&#10022; Make a little progress</span>
        </div>
      </div>
      <div style={styles.mockupChip}>
        <span style={styles.mockupChipDot} />
        THE METHOD · Recall, then connect.
      </div>
      <div style={styles.mockupDots}>
        {cards.map((_, i) => (
          <button key={i} onClick={() => setActive(i)} style={{ ...styles.mockupDot, ...(i === active ? styles.mockupDotActive : {}) }} aria-label={`Card ${i + 1}`} />
        ))}
      </div>
    </div>
  )
}

function FeatureCard({ icon, title, body, delay, visible }: { icon: string; title: string; body: string; delay: number; visible: boolean }) {
  return (
    <div style={{ ...styles.featureCard, opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(28px)", transition: `opacity 0.55s ease ${delay}ms, transform 0.55s ease ${delay}ms` }}>
      <div style={styles.featureIcon}>{icon}</div>
      <h3 style={styles.featureTitle}>{title}</h3>
      <p style={styles.featureBody}>{body}</p>
    </div>
  )
}

function StepCard({ num, title, body, delay, visible }: { num: number; title: string; body: string; delay: number; visible: boolean }) {
  return (
    <div style={{ ...styles.stepCard, opacity: visible ? 1 : 0, transform: visible ? "translateY(0)" : "translateY(28px)", transition: `opacity 0.55s ease ${delay}ms, transform 0.55s ease ${delay}ms` }}>
      <div style={styles.stepNum}>{String(num).padStart(2, "0")}</div>
      <h3 style={styles.stepTitle}>{title}</h3>
      <p style={styles.stepBody}>{body}</p>
    </div>
  )
}

const features = [
  { icon: "📄", title: "Upload anything", body: "Drop PDFs, PowerPoint slides, Word documents, or paste a YouTube link. StudyBot indexes it automatically in the background." },
  { icon: "💬", title: "Source-grounded answers", body: "Every answer cites the exact page or slide it came from. If the answer is not in your notes, StudyBot says so — it never guesses." },
  { icon: "🎙️", title: "Ask by voice", body: "Press mic, speak, pause. Your question is transcribed offline on your own PC with faster-whisper, shown to you, then answered in seconds." },
  { icon: "🗂️", title: "Subjects, not folders", body: "Organise notes by subject. Ask inside one subject or across all of them — the scope is always clear, never silently wrong." },
  { icon: "🔒", title: "Runs on your PC", body: "No cloud. No subscription. No data sent anywhere. The LLM, embeddings, and speech model all run locally on your own hardware." },
  { icon: "📱", title: "Installs as an app", body: "In Chrome or Edge, choose Install. On your phone, Add to Home Screen. Offline splash replaces a blank tab when the server is off." },
]

const steps = [
  { title: "Upload your material", body: "PDF, PPTX, DOCX, or a YouTube link. Indexing runs in the background with live progress — come back in a minute." },
  { title: "Ask a real question", body: "Type or speak. \"What is the difference between Sobel and Laplacian?\" StudyBot searches only the notes you gave it." },
  { title: "Read the cited answer", body: "Each answer includes numbered source chips — click one to jump to the exact page. Follow-up questions are handled correctly." },
]

const stats = [
  { value: 100, suffix: " MB", label: "Max upload size per file" },
  { value: 148, suffix: " MB", label: "Speech model, one-time download" },
  { value: 0,   suffix: "",    label: "Data sent to any cloud server" },
  { value: 3,   suffix: "B",   label: "Parameter LLM, fits in 4 GB VRAM" },
]

const SB_GREEN  = "#1e4d3f"
const SB_CREAM  = "#f5f0e8"
const SB_WARM   = "#ede8df"
const SB_TEXT   = "#1a1a1a"
const SB_MUTED  = "#6b6b6b"
const SB_BORDER = "#ddd8ce"

const styles: Record<string, React.CSSProperties> = {
  page: { fontFamily: "'Georgia','Times New Roman',serif", color: SB_TEXT, background: "#fff", minHeight: "100vh" },
  nav: { position: "fixed", top: 0, left: 0, right: 0, zIndex: 100, padding: "18px 0", transition: "background 0.25s,box-shadow 0.25s", background: "transparent" },
  navScrolled: { background: "rgba(245,240,232,0.92)", backdropFilter: "blur(12px)", boxShadow: "0 1px 0 rgba(0,0,0,0.08)" },
  navInner: { maxWidth: 1120, margin: "0 auto", padding: "0 32px", display: "flex", alignItems: "center", gap: 32 },
  logo: { display: "flex", alignItems: "center", gap: 10, textDecoration: "none", flexShrink: 0 },
  logoMark: { width: 32, height: 32, borderRadius: 8, background: SB_GREEN, color: "#fff", display: "flex", alignItems: "center", justifyContent: "center", fontFamily: "'Georgia',serif", fontWeight: 700, fontSize: 16 },
  logoText: { fontFamily: "'Georgia',serif", fontWeight: 700, fontSize: 18, color: SB_TEXT, letterSpacing: "-0.3px" },
  navLinks: { display: "flex", gap: 28, marginLeft: "auto" },
  navLink: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED, textDecoration: "none" },
  navActions: { display: "flex", gap: 12, alignItems: "center", marginLeft: 16 },
  btnGhost: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_TEXT, textDecoration: "none", padding: "8px 16px", borderRadius: 8 },
  btnPrimary: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: "#fff", background: SB_GREEN, textDecoration: "none", padding: "9px 20px", borderRadius: 8, fontWeight: 500 },
  hero: { background: SB_CREAM, paddingTop: 130, paddingBottom: 100, position: "relative", overflow: "hidden" },
  heroBgCircle1: { position: "absolute", right: -80, top: "50%", transform: "translateY(-50%)", width: 500, height: 500, borderRadius: "50%", background: "rgba(30,77,63,0.07)", pointerEvents: "none" },
  heroBgCircle2: { position: "absolute", right: 60, top: "60%", transform: "translateY(-50%)", width: 300, height: 300, borderRadius: "50%", background: "rgba(30,77,63,0.05)", pointerEvents: "none" },
  heroInner: { maxWidth: 1120, margin: "0 auto", padding: "0 32px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: 64, alignItems: "center" },
  heroLeft: { position: "relative", zIndex: 1 },
  heroRight: { position: "relative", zIndex: 1 },
  eyebrow: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", color: SB_MUTED, display: "flex", alignItems: "center", gap: 8, marginBottom: 20 },
  eyebrowDot: { width: 6, height: 6, borderRadius: "50%", background: "#e87c4e", display: "inline-block", flexShrink: 0 },
  heroHeading: { fontFamily: "'Georgia','Times New Roman',serif", fontSize: "clamp(2.8rem,5vw,4.2rem)", fontWeight: 700, lineHeight: 1.1, letterSpacing: "-0.03em", color: SB_TEXT, marginBottom: 20 },
  heroHeadingItalic: { fontStyle: "italic", color: SB_GREEN },
  heroSub: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 16, lineHeight: 1.65, color: SB_MUTED, maxWidth: 440, marginBottom: 36 },
  heroCtas: { display: "flex", gap: 16, flexWrap: "wrap", alignItems: "center" },
  btnHeroPrimary: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 15, fontWeight: 600, color: "#fff", background: SB_GREEN, textDecoration: "none", padding: "13px 28px", borderRadius: 10, display: "inline-flex", alignItems: "center", gap: 8, boxShadow: "0 2px 12px rgba(30,77,63,0.25)" },
  btnHeroGhost: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 15, color: SB_TEXT, background: "rgba(255,255,255,0.7)", border: `1px solid ${SB_BORDER}`, textDecoration: "none", padding: "12px 24px", borderRadius: 10, backdropFilter: "blur(4px)" },
  heroHint: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_MUTED, marginTop: 18, letterSpacing: "0.05em" },
  mockupWrapper: { position: "relative", maxWidth: 420, marginLeft: "auto" },
  mockupCard: { background: "#fff", border: `1px solid ${SB_BORDER}`, borderRadius: 20, padding: "28px 32px", boxShadow: "0 8px 40px rgba(0,0,0,0.10)", position: "relative", zIndex: 2 },
  mockupHeader: { display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 20 },
  mockupLabel: { fontFamily: "ui-monospace,monospace", fontSize: 10, letterSpacing: "0.12em", color: SB_MUTED, textTransform: "uppercase" },
  mockupCounter: { fontFamily: "ui-monospace,monospace", fontSize: 10, color: SB_MUTED, background: SB_WARM, padding: "3px 8px", borderRadius: 4 },
  mockupTag: { fontFamily: "ui-monospace,monospace", fontSize: 11, color: SB_GREEN, letterSpacing: "0.05em", marginBottom: 10 },
  mockupQ: { fontFamily: "'Georgia',serif", fontSize: 20, fontWeight: 700, lineHeight: 1.35, color: SB_TEXT, marginBottom: 12 },
  mockupHint: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, lineHeight: 1.55, marginBottom: 20 },
  mockupFooter: { borderTop: `1px solid ${SB_BORDER}`, paddingTop: 16 },
  mockupCta: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, color: SB_GREEN, fontWeight: 600, letterSpacing: "0.03em" },
  mockupChip: { position: "absolute", bottom: -22, left: -20, background: SB_GREEN, color: "#fff", fontFamily: "ui-monospace,monospace", fontSize: 11, fontWeight: 600, padding: "10px 18px", borderRadius: 10, boxShadow: "0 4px 16px rgba(30,77,63,0.35)", display: "flex", alignItems: "center", gap: 8, zIndex: 3, letterSpacing: "0.05em" },
  mockupChipDot: { width: 6, height: 6, borderRadius: "50%", background: "#7ae0b8", display: "inline-block" },
  mockupDots: { display: "flex", gap: 8, justifyContent: "center", marginTop: 44 },
  mockupDot: { width: 6, height: 6, borderRadius: "50%", background: SB_BORDER, border: "none", cursor: "pointer", padding: 0 },
  mockupDotActive: { background: SB_GREEN, transform: "scale(1.4)" },
  trustBar: { background: "#fff", borderBottom: `1px solid ${SB_BORDER}`, padding: "20px 32px", display: "flex", alignItems: "center", justifyContent: "center", gap: 20, flexWrap: "wrap" },
  trustLabel: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, letterSpacing: "0.05em", marginRight: 4 },
  trustIcons: { display: "flex", gap: 10, flexWrap: "wrap" },
  trustChip: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 12, fontWeight: 600, color: SB_GREEN, background: "rgba(30,77,63,0.08)", padding: "5px 14px", borderRadius: 100, letterSpacing: "0.04em", textTransform: "uppercase" },
  section: { background: "#fff", padding: "100px 0" },
  sectionAlt: { background: SB_CREAM, padding: "100px 0" },
  sectionInner: { maxWidth: 1120, margin: "0 auto", padding: "0 32px" },
  sectionEyebrow: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 11, fontWeight: 600, letterSpacing: "0.12em", color: SB_MUTED, marginBottom: 16 },
  sectionHeading: { fontFamily: "'Georgia','Times New Roman',serif", fontSize: "clamp(2rem,3.5vw,3rem)", fontWeight: 700, lineHeight: 1.15, letterSpacing: "-0.025em", color: SB_TEXT, marginBottom: 16 },
  sectionSub: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 16, color: SB_MUTED, lineHeight: 1.65, maxWidth: 520, marginBottom: 60 },
  featureGrid: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 24 },
  featureCard: { background: SB_CREAM, border: `1px solid ${SB_BORDER}`, borderRadius: 16, padding: "28px 28px 32px" },
  featureIcon: { fontSize: 28, marginBottom: 16 },
  featureTitle: { fontFamily: "'Georgia',serif", fontSize: 18, fontWeight: 700, color: SB_TEXT, marginBottom: 8 },
  featureBody: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED, lineHeight: 1.65 },
  stepsGrid: { display: "grid", gridTemplateColumns: "repeat(3,1fr)", gap: 32 },
  stepCard: { position: "relative", paddingLeft: 20, borderLeft: `3px solid ${SB_GREEN}` },
  stepNum: { fontFamily: "ui-monospace,monospace", fontSize: 11, fontWeight: 700, color: SB_GREEN, letterSpacing: "0.1em", marginBottom: 12 },
  stepTitle: { fontFamily: "'Georgia',serif", fontSize: 20, fontWeight: 700, color: SB_TEXT, marginBottom: 10, lineHeight: 1.3 },
  stepBody: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 14, color: SB_MUTED, lineHeight: 1.65 },
  statSection: { position: "relative", background: SB_GREEN, padding: "100px 0", overflow: "hidden" },
  statBg: { position: "absolute", inset: 0, backgroundImage: "radial-gradient(ellipse at 80% 50%,rgba(255,255,255,0.06) 0%,transparent 60%)", pointerEvents: "none" },
  statsGrid: { display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 32, marginTop: 56 },
  statCard: { textAlign: "center", padding: "32px 20px", borderRadius: 16, background: "rgba(255,255,255,0.07)", border: "1px solid rgba(255,255,255,0.12)" },
  statNum: { fontFamily: "'Georgia',serif", fontSize: "clamp(2rem,3vw,3rem)", fontWeight: 700, color: "#fff", marginBottom: 8 },
  statLabel: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: "rgba(255,255,255,0.6)", lineHeight: 1.5 },
  ctaSection: { background: SB_WARM, padding: "120px 0", textAlign: "center" },
  ctaInner: { maxWidth: 660, margin: "0 auto", padding: "0 32px", display: "flex", flexDirection: "column", alignItems: "center" },
  footer: { background: "#fff", borderTop: `1px solid ${SB_BORDER}`, padding: "40px 0" },
  footerInner: { maxWidth: 1120, margin: "0 auto", padding: "0 32px", display: "flex", alignItems: "center", justifyContent: "space-between", flexWrap: "wrap", gap: 16 },
  footerNote: { fontFamily: "ui-sans-serif,system-ui,sans-serif", fontSize: 13, color: SB_MUTED, letterSpacing: "0.03em" },
  fadeIn: { opacity: 1, transform: "translateY(0)", transition: "opacity 0.65s ease,transform 0.65s ease" },
  fadeOut: { opacity: 0, transform: "translateY(32px)", transition: "opacity 0.65s ease,transform 0.65s ease" },
}
