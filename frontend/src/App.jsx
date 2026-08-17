import { useState, useRef, useEffect } from "react"

const API = "http://127.0.0.1:8000"

const C = {
  bg:       "#0a0a14",
  sidebar:  "#0f1629",
  surface:  "#16213e",
  surfaceAlt:"#1a2744",
  border:   "#2a3a5c",
  accent:   "#e94560",
  teal:     "#00b4d8",
  muted:    "#8892a4",
  text:     "#e8eaf0",
  textSoft: "#b0b8cc",
  green:    "#22c55e",
  yellow:   "#f59e0b",
  red:      "#ef4444",
}

// ── helpers ───────────────────────────────────────────────────────────────────
function scoreColor(s) {
  return s >= 7 ? C.green : s >= 4 ? C.yellow : C.red
}
function scoreLabel(s) {
  return s >= 8 ? "Excellent" : s >= 6 ? "Good" : s >= 4 ? "Developing" : "Keep going"
}
function getDifficulty(scores) {
  if (!scores || scores.length < 2) return "medium"
  const recent = scores.slice(-3)
  const avg = recent.reduce((a, b) => a + b, 0) / recent.length
  return avg >= 7 ? "hard" : avg >= 4 ? "medium" : "easy"
}
function formatTime(s) {
  const m = Math.floor(s / 60)
  const sec = String(s % 60).padStart(2, "0")
  return `${m}:${sec}`
}
function formatDate(iso) {
  if (!iso) return ""
  const d = new Date(iso)
  const diff = Math.floor((Date.now() - d.getTime()) / 86400000)
  if (diff === 0) return "Today"
  if (diff === 1) return "Yesterday"
  if (diff < 7)  return `${diff}d ago`
  return d.toLocaleDateString()
}

// ── Score bar (inline) ────────────────────────────────────────────────────────
function InlineScore({ score, feedback }) {
  if (score === null || score === undefined) return null
  const color = scoreColor(score)
  const label = scoreLabel(score)
  // Hide raw API/quota error messages from the feedback display
  const isApiError = feedback && (
    feedback.toLowerCase().includes("quota") ||
    feedback.toLowerCase().includes("evaluation error") ||
    feedback.toLowerCase().includes("rate limit") ||
    feedback.toLowerCase().includes("429")
  )
  const displayFeedback = isApiError ? "Evaluation unavailable right now." : (feedback || "")
  return (
    <div style={{
      borderTop: `1px solid ${C.border}`,
      marginTop: 10, paddingTop: 8,
      display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: 12
    }}>
      <p style={{ margin: 0, fontSize: 11, color: C.muted, fontStyle: "italic",
                  fontFamily: "sans-serif", lineHeight: 1.5, flex: 1 }}>
        {displayFeedback}
      </p>
      <span style={{ fontSize: 12, fontWeight: 700, color, fontFamily: "sans-serif",
                     whiteSpace: "nowrap" }}>
        {score}/10 · {label}
      </span>
    </div>
  )
}

// ── Message bubble ────────────────────────────────────────────────────────────
function Message({ msg }) {
  if (msg.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 14 }}>
        <div style={{
          maxWidth: "75%", padding: "10px 14px",
          borderRadius: "16px 16px 4px 16px",
          background: "#1e3a6e", border: "1px solid #2a4a8a",
          color: C.text, fontSize: 14, fontFamily: "sans-serif", lineHeight: 1.55
        }}>
          <span style={{ fontSize: 10, color: C.muted, display: "block",
                         marginBottom: 3, textAlign: "right" }}>You</span>
          {msg.text}
        </div>
      </div>
    )
  }

  if (msg.role === "tutor") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-start", marginBottom: 14 }}>
        <div style={{
          maxWidth: "85%", padding: "10px 14px",
          borderRadius: "16px 16px 16px 4px",
          background: C.surface, border: `1px solid ${C.border}`,
          color: C.text, fontSize: 14, fontFamily: "sans-serif", lineHeight: 1.55
        }}>
          <span style={{ fontSize: 10, color: C.teal, display: "block",
                         marginBottom: 4, fontWeight: 600 }}>🧑‍🏫 Tutor</span>
          {msg.text || <span style={{ opacity: 0.4 }}>▌</span>}
          <InlineScore score={msg.score} feedback={msg.feedback} />
        </div>
      </div>
    )
  }

  if (msg.role === "error") {
    return (
      <div style={{
        padding: "10px 14px", borderRadius: 10, marginBottom: 12,
        background: "#2d1515", border: "1px solid #6b2020",
        color: "#fca5a5", fontSize: 13, fontFamily: "sans-serif"
      }}>
        ⚠️ {msg.text}
      </div>
    )
  }
  return null
}

// ── Progress tab ──────────────────────────────────────────────────────────────
function ProgressTab({ scores }) {
  if (!scores.length) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 240 }}>
      <p style={{ color: C.muted, fontFamily: "sans-serif", fontSize: 14 }}>
        No scores yet — share what you know to start tracking progress.
      </p>
    </div>
  )
  const w = 480, h = 200, pad = 32
  const step = (w - pad * 2) / Math.max(scores.length - 1, 1)
  const pts = scores.map((s, i) => ({
    x: pad + i * step,
    y: h - pad - (s / 10) * (h - pad * 2)
  }))
  const path = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x} ${p.y}`).join(" ")
  const avg = (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
  return (
    <div style={{ padding: 24 }}>
      <p style={{ color: C.textSoft, fontFamily: "sans-serif", fontSize: 13, margin: "0 0 16px" }}>
        Average: <strong style={{ color: C.teal }}>{avg}/10</strong> over {scores.length} response{scores.length !== 1 ? "s" : ""}
      </p>
      <svg width="100%" viewBox={`0 0 ${w} ${h}`} style={{ overflow: "visible" }}>
        {[0, 3, 6, 10].map(v => {
          const y = h - pad - (v / 10) * (h - pad * 2)
          return (
            <g key={v}>
              <line x1={pad} y1={y} x2={w - pad} y2={y}
                    stroke="#2a3a5c" strokeWidth="1" strokeDasharray="4 4" />
              <text x={pad - 6} y={y + 4} fill={C.muted} fontSize="10"
                    textAnchor="end" fontFamily="sans-serif">{v}</text>
            </g>
          )
        })}
        <path d={path} fill="none" stroke={C.teal} strokeWidth="2.5"
              strokeLinecap="round" strokeLinejoin="round" />
        {pts.map((p, i) => (
          <circle key={i} cx={p.x} cy={p.y} r="5"
                  fill={scoreColor(scores[i])} stroke={C.bg} strokeWidth="2" />
        ))}
        {pts.map((p, i) => (
          <text key={i} x={p.x} y={p.y - 10} fill={C.text} fontSize="10"
                textAnchor="middle" fontFamily="sans-serif">{scores[i]}</text>
        ))}
      </svg>
    </div>
  )
}

// ── Concepts tab ──────────────────────────────────────────────────────────────
function ConceptsTab({ concepts }) {
  if (!concepts.length) return (
    <div style={{ display: "flex", alignItems: "center", justifyContent: "center", height: 240 }}>
      <p style={{ color: C.muted, fontFamily: "sans-serif", fontSize: 14 }}>
        No concepts tracked yet — keep chatting!
      </p>
    </div>
  )
  return (
    <div style={{ padding: 24, display: "flex", flexWrap: "wrap", gap: 10 }}>
      {concepts.map((c, i) => {
        const color = c.understood ? C.green : C.red
        return (
          <div key={i} style={{
            padding: "8px 14px", borderRadius: 20,
            background: c.understood ? "#14532d33" : "#7f1d1d33",
            border: `1px solid ${color}66`,
            display: "flex", alignItems: "center", gap: 8
          }}>
            <span style={{ fontSize: 13 }}>{c.understood ? "✅" : "🔄"}</span>
            <span style={{ color: C.text, fontSize: 13, fontFamily: "sans-serif" }}>{c.concept}</span>
            <span style={{ color, fontSize: 11, fontFamily: "sans-serif", fontWeight: 700 }}>
              {c.score}/10
            </span>
          </div>
        )
      })}
    </div>
  )
}

// ── Coverage tab ──────────────────────────────────────────────────────────────
function CoverageTab({ concepts, scores, messages }) {
  const totalMsgs = messages.filter(m => m.role === "user").length
  const understood = concepts.filter(c => c.understood).length
  const developing = concepts.filter(c => !c.understood).length
  const coveragePct = concepts.length > 0
    ? Math.min(100, Math.round((understood / Math.max(concepts.length, 1)) * 100))
    : 0

  const avgScore = scores.length
    ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
    : "--"

  return (
    <div style={{ padding: 24 }}>

      {/* overview cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 10, marginBottom: 24 }}>
        {[
          { label: "Exchanges", value: totalMsgs, color: C.teal },
          { label: "Concepts explored", value: concepts.length, color: C.teal },
          { label: "Understood", value: understood, color: C.green },
          { label: "Still developing", value: developing, color: C.yellow },
        ].map((item, i) => (
          <div key={i} style={{
            background: C.surface, border: `1px solid ${C.border}`,
            borderRadius: 10, padding: "12px 14px", textAlign: "center"
          }}>
            <div style={{ fontSize: 22, fontWeight: 700, color: item.color,
                          fontFamily: "sans-serif" }}>{item.value}</div>
            <div style={{ fontSize: 11, color: C.muted, fontFamily: "sans-serif",
                          marginTop: 3 }}>{item.label}</div>
          </div>
        ))}
      </div>

      {/* understanding bar */}
      <p style={{ color: C.textSoft, fontSize: 13, fontFamily: "sans-serif",
                  margin: "0 0 8px" }}>
        Overall understanding
      </p>
      <div style={{ background: C.border, borderRadius: 6, height: 10, overflow: "hidden", marginBottom: 6 }}>
        <div style={{
          height: "100%", borderRadius: 6,
          width: `${coveragePct}%`,
          background: coveragePct >= 70 ? C.green : coveragePct >= 40 ? C.yellow : C.red,
          transition: "width 0.8s ease"
        }} />
      </div>
      <p style={{ color: C.muted, fontSize: 11, fontFamily: "sans-serif",
                  margin: "0 0 24px" }}>
        {coveragePct}% of explored concepts understood
      </p>

      {/* per-concept breakdown */}
      {concepts.length > 0 && (
        <>
          <p style={{ color: C.textSoft, fontSize: 13, fontFamily: "sans-serif",
                      margin: "0 0 10px", fontWeight: 600 }}>
            Topic breakdown
          </p>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {concepts.map((c, i) => (
              <div key={i} style={{
                background: C.surface, border: `1px solid ${C.border}`,
                borderRadius: 8, padding: "8px 14px",
                display: "flex", alignItems: "center", gap: 12
              }}>
                <span style={{ fontSize: 12 }}>{c.understood ? "✅" : "🔄"}</span>
                <span style={{ flex: 1, fontSize: 13, color: C.text,
                               fontFamily: "sans-serif" }}>{c.concept}</span>
                <div style={{ width: 80, background: C.border, borderRadius: 4,
                              height: 5, overflow: "hidden" }}>
                  <div style={{
                    height: "100%", borderRadius: 4,
                    width: `${(c.score / 10) * 100}%`,
                    background: scoreColor(c.score)
                  }} />
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, color: scoreColor(c.score),
                               fontFamily: "sans-serif", minWidth: 36, textAlign: "right" }}>
                  {c.score}/10
                </span>
              </div>
            ))}
          </div>
        </>
      )}

      {concepts.length === 0 && (
        <div style={{ textAlign: "center", padding: "40px 0" }}>
          <p style={{ color: C.muted, fontFamily: "sans-serif", fontSize: 14 }}>
            Start sharing your understanding in the Chat tab to see coverage data here.
          </p>
        </div>
      )}
    </div>
  )
}


// ── Sidebar nav item ──────────────────────────────────────────────────────────
function NavItem({ icon, label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      style={{
        width: "100%", display: "flex", alignItems: "center", gap: 10,
        padding: "9px 14px", borderRadius: 8, border: "none", cursor: "pointer",
        background: active ? C.surfaceAlt : "transparent",
        color: active ? C.text : C.muted,
        fontSize: 13, fontFamily: "sans-serif",
        fontWeight: active ? 600 : 400,
        transition: "all 0.15s",
        borderLeft: active ? `3px solid ${C.accent}` : "3px solid transparent",
        textAlign: "left"
      }}
    >
      <span style={{ fontSize: 15 }}>{icon}</span>
      {label}
    </button>
  )
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [sessionId,  setSessionId]  = useState(() => localStorage.getItem("session_id") || null)
  const [documents,  setDocuments]  = useState(() => {
    try { return JSON.parse(localStorage.getItem("documents") || "[]") } catch { return [] }
  })
  const [messages,   setMessages]   = useState([])
  const [input,      setInput]      = useState("")
  const [loading,    setLoading]    = useState(false)
  const [tab,        setTab]        = useState("chat")
  const [scores,     setScores]     = useState([])
  const [concepts,   setConcepts]   = useState([])
  const [elapsed,    setElapsed]    = useState(0)
  const [uploading,  setUploading]  = useState(false)
  const [uploadMsg,  setUploadMsg]  = useState("")
  const [dueConcepts, setDueConcepts] = useState([])
  const [pendingFiles, setPendingFiles] = useState([])
  const [dragging,   setDragging]   = useState(false)
  const [pastSessions, setPastSessions] = useState([])
  const bottomRef  = useRef(null)
  const timerRef   = useRef(null)
  const addFileRef = useRef(null)
  const mainFileRef = useRef(null)

  // ── load past sessions list ────────────────────────────────────────────────
  const loadPastSessions = () => {
    fetch(`${API}/sessions`)
      .then(r => r.ok ? r.json() : { sessions: [] })
      .then(d => setPastSessions(d.sessions || []))
      .catch(() => {})
  }

  const resumePastSession = async (id) => {
    if (sessionId && messages.length > 0) {
      if (!window.confirm("Switch to a past session? Your current session is already saved.")) return
    }
    try {
      const r = await fetch(`${API}/session/resume/${id}`)
      if (!r.ok) { alert("Could not load that session."); return }
      const data = await r.json()
      const restored = data.messages.map(m => ({
        role:     m.role === "assistant" ? "tutor" : m.role,
        text:     m.content,
        score:    m.score    ?? null,
        feedback: m.feedback ?? "",
      }))
      localStorage.setItem("session_id", id)
      localStorage.setItem("documents", JSON.stringify(data.sources || []))
      clearInterval(timerRef.current)
      setElapsed(0)
      setSessionId(id)
      setMessages(restored)
      setScores(data.scores   || [])
      setConcepts(data.concepts || [])
      setDocuments(data.sources || [])
      setTab("chat")
    } catch { alert("Failed to resume session.") }
  }

  useEffect(() => { loadPastSessions() }, [])

  // ── auto-resume persisted session on page load ────────────────────────────
  useEffect(() => {
    const savedId   = localStorage.getItem("session_id")
    const savedDocs = (() => { try { return JSON.parse(localStorage.getItem("documents") || "[]") } catch { return [] } })()
    if (!savedId) return

    fetch(`${API}/session/resume/${savedId}`)
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return
        // Map backend role names to frontend role names
        const restored = data.messages.map(m => ({
          role:     m.role === "assistant" ? "tutor" : m.role,
          text:     m.content,
          score:    m.score    ?? null,
          feedback: m.feedback ?? "",
        }))
        setSessionId(savedId)
        setMessages(restored)
        setScores(data.scores   || [])
        setConcepts(data.concepts || [])
        setDocuments(data.sources?.length ? data.sources : savedDocs)
      })
      .catch(() => { /* server not running yet — silently ignore */ })
  }, []) // runs once on mount

  // session timer
  useEffect(() => {
    if (!sessionId) return
    timerRef.current = setInterval(() => setElapsed(e => e + 1), 1000)
    return () => clearInterval(timerRef.current)
  }, [sessionId])

  // fetch due concepts on load and whenever tab switches to "review"
  useEffect(() => {
    fetch(`${API}/concepts/due`)
      .then(r => r.ok ? r.json() : { concepts: [] })
      .then(d => setDueConcepts(d.concepts || []))
      .catch(() => {})
  }, [tab])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  const difficulty   = getDifficulty(scores)
  const diffColor    = difficulty === "hard" ? "#a78bfa" : difficulty === "medium" ? C.yellow : C.green
  const diffBg       = difficulty === "hard" ? "#7c3aed22" : difficulty === "medium" ? "#d9770622" : "#16a34a22"
  const diffBorder   = difficulty === "hard" ? "#7c3aed55" : difficulty === "medium" ? "#d9770655" : "#16a34a55"
  const avgScore     = scores.length
    ? (scores.reduce((a, b) => a + b, 0) / scores.length).toFixed(1)
    : null

  const newSession = () => {
    if (messages.length > 0) {
      const shouldExport = window.confirm(
        "Export this session as PDF before starting fresh?"
      )
      if (shouldExport) {
        const a = document.createElement("a")
        a.href = `${API}/session/${sessionId}/export`
        a.download = "mentormind_session.pdf"
        a.click()
      }
    }
    localStorage.removeItem("session_id")
    localStorage.removeItem("documents")
    clearInterval(timerRef.current)
    setSessionId(null); setDocuments([]); setMessages([])
    setScores([]); setConcepts([]); setInput("")
    setLoading(false); setElapsed(0); setTab("chat")
  }

  // ── clear ChromaDB knowledge base ──────────────────────────────────────────
  const clearKnowledgeBase = async () => {
    if (!window.confirm("This will delete all uploaded documents from the knowledge base. Are you sure?")) return
    try {
      const res = await fetch(`${API}/documents`, { method: "DELETE" })
      if (!res.ok) throw new Error()
      localStorage.removeItem("documents")
      setDocuments([])
      setUploadMsg("Knowledge base cleared")
      setTimeout(() => setUploadMsg(""), 3000)
    } catch {
      setUploadMsg("Failed to clear")
      setTimeout(() => setUploadMsg(""), 3000)
    }
  }

  // ── add more files to existing session ─────────────────────────────────────
  const addFiles = async (fileList) => {
    const files = Array.from(fileList).filter(
      f => f.type === "application/pdf" || f.name.endsWith(".pdf") || f.name.endsWith(".txt")
    )
    if (!files.length) return
    setUploading(true)
    setUploadMsg("Uploading...")
    try {
      const form = new FormData()
      files.forEach(f => form.append("files", f))
      const upRes = await fetch(`${API}/upload`, { method: "POST", body: form })
      if (!upRes.ok) throw new Error("Upload failed")
      const upData = await upRes.json()
      const newSources = upData.sources || []
      const merged = [...new Set([...documents, ...newSources])]
      localStorage.setItem("documents", JSON.stringify(merged))
      setDocuments(merged)
      setUploadMsg(`Added ${files.length} file${files.length > 1 ? "s" : ""}`)
      setTimeout(() => setUploadMsg(""), 3000)
    } catch (e) {
      setUploadMsg("Upload failed")
      setTimeout(() => setUploadMsg(""), 3000)
    }
    setUploading(false)
  }

  // ── send message ────────────────────────────────────────────────────────────
  const sendMessage = async () => {
    if (!input.trim() || loading || !sessionId) return
    const userMessage = input.trim()
    setInput("")
    setLoading(true)
    setMessages(prev => [...prev, { role: "user", text: userMessage }])

    try {
      const res = await fetch(`${API}/session/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ session_id: sessionId, message: userMessage })
      })
      if (!res.ok) throw new Error(res.status === 404 ? "404" : `Error ${res.status}`)

      const data = await res.json()
      setMessages(prev => [...prev, {
        role:     "tutor",
        text:     data.reply || "(no response)",
        score:    data.score ?? null,
        feedback: data.feedback ?? ""
      }])
      if (data.score !== null && data.score !== undefined) {
        setScores(prev => [...prev, data.score])
        // refresh SR due list after a concept is scored
        fetch(`${API}/concepts/due`)
          .then(r => r.ok ? r.json() : { concepts: [] })
          .then(d => setDueConcepts(d.concepts || []))
          .catch(() => {})
      }

      try {
        const cRes = await fetch(`${API}/session/${sessionId}/concepts`)
        if (cRes.ok) {
          const cData = await cRes.json()
          setConcepts(cData.concepts || [])
        }
      } catch { /* ignore */ }

    } catch (e) {
      setMessages(prev => [...prev, {
        role: "error",
        text: e.message.includes("404")
          ? "Session expired - click New Session to start fresh."
          : `Could not reach backend: ${e.message}`
      }])
    }
    setLoading(false)
  }

  // ── start new session from inline upload ────────────────────────────────────
  const handlePendingFiles = (incoming) => {
    const arr = Array.from(incoming).filter(
      f => f.type === "application/pdf" || f.name.endsWith(".pdf") || f.name.endsWith(".txt")
    )
    setPendingFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...arr.filter(f => !names.has(f.name))]
    })
  }

  const startSession = async () => {
    if (!pendingFiles.length) return
    setUploading(true)
    setUploadMsg("Uploading documents...")
    const form = new FormData()
    pendingFiles.forEach(f => form.append("files", f))
    try {
      const upRes  = await fetch(`${API}/upload`, { method: "POST", body: form })
      if (!upRes.ok) throw new Error("Upload failed")
      const upData = await upRes.json()
      const sources = upData.sources || []
      setUploadMsg("Starting session...")
      const sRes  = await fetch(`${API}/session/start`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ sources })
      })
      if (!sRes.ok) throw new Error("Session start failed")
      const sData = await sRes.json()
      localStorage.setItem("session_id", sData.session_id)
      localStorage.setItem("documents", JSON.stringify(sources))
      setSessionId(sData.session_id)
      setDocuments(sources)
      setPendingFiles([])
      setUploadMsg("")
      loadPastSessions()
    } catch (e) {
      setUploadMsg("Error: " + e.message)
    }
    setUploading(false)
  }

  // ── main layout ─────────────────────────────────────────────────────────────
  return (
    <div style={{
      display: "flex", height: "100vh", overflow: "hidden",
      background: C.bg, fontFamily: "sans-serif"
    }}>

      {/* ── Sidebar ── */}
      <div style={{
        width: 220, height: "100vh", background: C.sidebar,
        borderRight: `1px solid ${C.border}`,
        display: "flex", flexDirection: "column",
        padding: "20px 12px", flexShrink: 0,
        overflowY: "auto",
        scrollbarWidth: "thin", scrollbarColor: `${C.border} transparent`
      }}>
        {/* Logo */}
        <div style={{ marginBottom: 20, paddingLeft: 4 }}>
          <h1 style={{ margin: 0, fontSize: 20, fontWeight: 800, color: C.text }}>
            🧠 <span style={{ color: C.accent }}>Mentor</span>Mind
          </h1>
        </div>

        {/* Document */}
        <div style={{
          background: "#0369a122", border: "1px solid #0369a144",
          borderRadius: 8, padding: "7px 10px", marginBottom: 8
        }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <p style={{ margin: 0, fontSize: 10, color: C.muted }}>Documents</p>
            <button
              onClick={() => addFileRef.current?.click()}
              disabled={uploading}
              title="Add more files"
              style={{
                background: "none", border: `1px solid ${C.border}`,
                borderRadius: 4, color: uploading ? C.muted : C.teal,
                fontSize: 13, cursor: uploading ? "not-allowed" : "pointer",
                padding: "1px 6px", lineHeight: 1.4
              }}
            >+</button>
          </div>
          {documents.map((d, i) => (
            <p key={i} style={{ margin: "3px 0 0", fontSize: 11,
                                 color: "#38bdf8", wordBreak: "break-word" }}>📄 {d}</p>
          ))}
          {uploadMsg && (
            <p style={{ margin: "4px 0 0", fontSize: 10,
                        color: uploadMsg.startsWith("Added") || uploadMsg.startsWith("Knowledge") ? C.green : C.red }}>
              {uploadMsg}
            </p>
          )}
        </div>
        <input
          ref={addFileRef} type="file" multiple accept=".pdf,.txt"
          style={{ display: "none" }}
          onChange={e => { addFiles(e.target.files); e.target.value = "" }}
        />

        <div style={{ marginBottom: 10 }} />

        {/* Nav — only when session active */}
        {sessionId && (
          <div style={{ display: "flex", flexDirection: "column", gap: 3, marginBottom: 20 }}>
            <NavItem icon="💬" label="Chat"     active={tab === "chat"}     onClick={() => setTab("chat")} />
            <NavItem icon="📈" label="Progress" active={tab === "progress"} onClick={() => setTab("progress")} />
            <NavItem icon="🗺️"  label="Concepts" active={tab === "concepts"} onClick={() => setTab("concepts")} />
            <NavItem icon="📊" label="Coverage" active={tab === "coverage"} onClick={() => setTab("coverage")} />
            <div style={{ position: "relative" }}>
              <NavItem icon="🔁" label="Review" active={tab === "review"} onClick={() => setTab("review")} />
              {dueConcepts.length > 0 && (
                <span style={{
                  position: "absolute", top: 4, right: 8,
                  background: C.accent, color: "white",
                  fontSize: 9, fontWeight: 700, borderRadius: 10,
                  padding: "1px 5px", pointerEvents: "none"
                }}>{dueConcepts.length}</span>
              )}
            </div>
          </div>
        )}

        {sessionId && <div style={{ height: 1, background: C.border, margin: "0 4px 16px" }} />}

        {/* Stats — only when session active */}
        {sessionId && <div style={{ display: "flex", flexDirection: "column", gap: 12, marginBottom: 20 }}>

          {/* Difficulty */}
          <div>
            <p style={{ margin: "0 0 5px", fontSize: 10, color: C.muted }}>Difficulty</p>
            <span style={{
              padding: "3px 10px", borderRadius: 20, fontSize: 11, fontWeight: 700,
              background: diffBg, color: diffColor, border: `1px solid ${diffBorder}`
            }}>
              {difficulty === "hard" ? "🔥 Hard" : difficulty === "medium" ? "⚡ Medium" : "🌱 Easy"}
            </span>
          </div>

          {/* Score */}
          <div>
            <p style={{ margin: "0 0 4px", fontSize: 10, color: C.muted }}>Avg score</p>
            <span style={{ fontSize: 20, fontWeight: 700,
                           color: avgScore ? scoreColor(parseFloat(avgScore)) : C.muted }}>
              {avgScore ?? "--"}
              <span style={{ fontSize: 11, color: C.muted, fontWeight: 400 }}>/10</span>
            </span>
          </div>

          {/* Mini stats row */}
          <div>
            <p style={{ margin: 0, fontSize: 10, color: C.muted }}>Turns</p>
            <p style={{ margin: 0, fontSize: 15, fontWeight: 700, color: C.teal }}>
              {messages.filter(m => m.role === "user").length}
            </p>
          </div>
        </div>}

        {sessionId && <div style={{ height: 1, background: C.border, margin: "0 4px 16px" }} />}

        {/* Buttons */}
        <div style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: "auto" }}>
          {sessionId && <button
            onClick={() => window.open(`${API}/session/${sessionId}/export`, "_blank")}
            style={{
              padding: "9px 12px", borderRadius: 8, border: `1px solid ${C.border}`,
              background: "transparent", color: C.textSoft,
              fontSize: 12, cursor: "pointer", fontFamily: "sans-serif"
            }}
          >
            📄 Export PDF
          </button>}
          <button
            onClick={newSession}
            style={{
              padding: "9px 12px", borderRadius: 8, border: `1px solid ${C.border}`,
              background: "transparent", color: C.muted,
              fontSize: 12, cursor: "pointer", fontFamily: "sans-serif"
            }}
          >
            &#8635; New Session
          </button>
          <button
            onClick={clearKnowledgeBase}
            title="Remove all uploaded documents from the knowledge base"
            style={{
              padding: "9px 12px", borderRadius: 8,
              border: `1px solid #7f1d1d55`,
              background: "transparent", color: "#f87171",
              fontSize: 12, cursor: "pointer", fontFamily: "sans-serif"
            }}
          >
            🗑 Clear knowledge base
          </button>
        </div>
      </div>

      {/* ── Past Sessions Column ── */}
      <div style={{
        width: 200, height: "100vh", background: C.sidebar,
        borderRight: `1px solid ${C.border}`,
        display: "flex", flexDirection: "column",
        flexShrink: 0
      }}>
        <div style={{
          padding: "16px 12px 10px",
          borderBottom: `1px solid ${C.border}`
        }}>
          <p style={{ margin: 0, fontSize: 10, fontWeight: 700,
                      color: C.muted, letterSpacing: "0.08em" }}>
            PAST SESSIONS
          </p>
        </div>

        {pastSessions.length === 0 ? (
          <div style={{ flex: 1, display: "flex", alignItems: "center",
                        justifyContent: "center", padding: 16 }}>
            <p style={{ margin: 0, fontSize: 11, color: C.muted,
                        textAlign: "center", lineHeight: 1.5 }}>
              No sessions yet. Start one to see your history here.
            </p>
          </div>
        ) : (
          <div style={{
            flex: 1, overflowY: "auto", padding: "8px",
            display: "flex", flexDirection: "column", gap: 6,
            scrollbarWidth: "thin", scrollbarColor: `${C.border} transparent`
          }}>
            {pastSessions.map((s, i) => {
              const isCurrent = s.session_id === sessionId
              const docNames = s.sources.length
                ? s.sources.map(src => src.replace(/\.[^.]+$/, "")).join(", ")
                : "No document"
              return (
                <div
                  key={i}
                  style={{
                    borderRadius: 8, padding: "8px 10px",
                    background: isCurrent ? C.surfaceAlt : "transparent",
                    border: `1px solid ${isCurrent ? C.accent + "66" : C.border}`,
                    transition: "background 0.15s"
                  }}
                  onMouseEnter={e => { if (!isCurrent) e.currentTarget.style.background = C.surfaceAlt }}
                  onMouseLeave={e => { if (!isCurrent) e.currentTarget.style.background = "transparent" }}
                >
                  {/* Session info — clickable */}
                  <button
                    onClick={() => !isCurrent && resumePastSession(s.session_id)}
                    style={{
                      width: "100%", textAlign: "left", background: "none",
                      border: "none", padding: 0,
                      cursor: isCurrent ? "default" : "pointer"
                    }}
                  >
                    <p style={{
                      margin: 0, fontSize: 12, fontWeight: 600,
                      color: isCurrent ? C.accent : C.text,
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis"
                    }}>
                      {isCurrent && "* "}{docNames}
                    </p>
                    <p style={{ margin: "3px 0 0", fontSize: 10, color: C.muted }}>
                      {s.turns} turn{s.turns !== 1 ? "s" : ""} · {formatDate(s.last_active)}
                    </p>
                  </button>

                  {/* Delete button — only on non-current sessions */}
                  {!isCurrent && (
                    <button
                      title="Delete session"
                      onClick={async () => {
                        if (!window.confirm("Delete this session permanently?")) return
                        await fetch(`${API}/session/${s.session_id}`, { method: "DELETE" })
                        setPastSessions(prev => prev.filter((_, j) => j !== i))
                      }}
                      style={{
                        marginTop: 6, width: "100%", padding: "3px 0",
                        borderRadius: 5, border: `1px solid #7f1d1d44`,
                        background: "transparent", color: "#f8717166",
                        fontSize: 11, cursor: "pointer",
                        transition: "all 0.15s"
                      }}
                      onMouseEnter={e => {
                        e.currentTarget.style.background = "#7f1d1d33"
                        e.currentTarget.style.color = C.red
                      }}
                      onMouseLeave={e => {
                        e.currentTarget.style.background = "transparent"
                        e.currentTarget.style.color = "#f8717166"
                      }}
                    >
                      Delete
                    </button>
                  )}
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* ── Main content ── */}
      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", height: "100vh" }}>

        {/* ── Active session tabs ── */}
        {sessionId && tab === "progress" && (
          <div style={{ flex: 1, overflowY: "auto" }}>
            <ProgressTab scores={scores} />
          </div>
        )}

        {sessionId && tab === "concepts" && (
          <div style={{ flex: 1, overflowY: "auto" }}>
            <ConceptsTab concepts={concepts} />
          </div>
        )}

        {sessionId && tab === "coverage" && (
          <div style={{ flex: 1, overflowY: "auto" }}>
            <CoverageTab concepts={concepts} scores={scores} messages={messages} />
          </div>
        )}

        {sessionId && tab === "review" && (
          <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
            <p style={{ color: C.textSoft, fontSize: 13, margin: "0 0 6px" }}>
              Spaced repetition — concepts due for review today
            </p>
            <p style={{ color: C.muted, fontSize: 11, margin: "0 0 20px" }}>
              Each concept's interval grows as your scores improve (SM-2 algorithm).
              Click <strong style={{ color: C.text }}>Review Now</strong> to focus on a topic.
            </p>

            {dueConcepts.length === 0 ? (
              <div style={{ textAlign: "center", padding: "60px 0" }}>
                <div style={{ fontSize: 36, marginBottom: 10 }}>🎉</div>
                <p style={{ color: C.text, fontSize: 15, fontWeight: 600, margin: 0 }}>
                  All caught up!
                </p>
                <p style={{ color: C.muted, fontSize: 13, marginTop: 6 }}>
                  No concepts are due for review. Keep studying to build your schedule.
                </p>
              </div>
            ) : (
              <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
                {dueConcepts.map((c, i) => {
                  const daysOverdue = c.due_date
                    ? Math.max(0, Math.floor(
                        (Date.now() - new Date(c.due_date).getTime()) / 86400000
                      ))
                    : 0
                  const scoreCol = c.last_score >= 7 ? C.green : c.last_score >= 4 ? C.yellow : C.red
                  return (
                    <div key={i} style={{
                      background: C.surface, border: `1px solid ${C.border}`,
                      borderRadius: 10, padding: "14px 16px",
                      display: "flex", alignItems: "center", gap: 14
                    }}>
                      <div style={{ flex: 1 }}>
                        <p style={{ margin: 0, fontSize: 14, fontWeight: 600,
                                    color: C.text, textTransform: "capitalize" }}>
                          {c.concept}
                        </p>
                        <p style={{ margin: "4px 0 0", fontSize: 11, color: C.muted }}>
                          {c.repetitions} successful review{c.repetitions !== 1 ? "s" : ""} ·{" "}
                          {c.attempts} attempt{c.attempts !== 1 ? "s" : ""} ·{" "}
                          {daysOverdue > 0 ? `${daysOverdue}d overdue` : "due today"}
                        </p>
                      </div>
                      <span style={{
                        fontSize: 12, fontWeight: 700, color: scoreCol,
                        minWidth: 40, textAlign: "right"
                      }}>
                        {c.last_score}/10
                      </span>
                      <button
                        onClick={() => {
                          setInput("")
                          setTab("chat")
                          setTimeout(() => {
                            setMessages(prev => [...prev, {
                              role: "tutor",
                              text: `Let's revisit **${c.concept}**.\n\n📎 If you studied this from a specific document, make sure to add it using the + button in the sidebar first.\n\nWhen you're ready, tell me what you know about it in your own words.`,
                              score: null,
                              feedback: ""
                            }])
                          }, 100)
                        }}
                        style={{
                          padding: "7px 14px", borderRadius: 8, border: "none",
                          background: `linear-gradient(135deg, ${C.accent}, #c0392b)`,
                          color: "white", fontSize: 12, fontWeight: 600,
                          cursor: "pointer", whiteSpace: "nowrap"
                        }}
                      >
                        Review Now &#8594;
                      </button>
                      <button
                        title="Remove from review queue"
                        onClick={async () => {
                          await fetch(`${API}/concepts/${encodeURIComponent(c.concept)}`, { method: "DELETE" })
                          setDueConcepts(prev => prev.filter((_, j) => j !== i))
                        }}
                        style={{
                          padding: "7px 10px", borderRadius: 8,
                          border: `1px solid #7f1d1d55`,
                          background: "transparent", color: "#f87171",
                          fontSize: 13, fontWeight: 700,
                          cursor: "pointer", lineHeight: 1
                        }}
                      >
                        x
                      </button>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {/* Chat — shown always (handles both no-session upload and active chat) */}
        {(!sessionId || tab === "chat") && (
          <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>

            {/* Messages / Upload area */}
            <div style={{
              flex: 1, overflowY: "auto", padding: "24px 28px 12px",
              scrollbarWidth: "thin", scrollbarColor: `${C.border} transparent`
            }}>
              {/* ── No session: compact upload card ── */}
              {!sessionId && (
                <div style={{
                  display: "flex", alignItems: "center", justifyContent: "center",
                  height: "100%"
                }}>
                  <div style={{
                    width: "100%", maxWidth: 420, background: C.surface,
                    border: `1px solid ${C.border}`, borderRadius: 16,
                    padding: "28px 24px"
                  }}>
                    <p style={{ margin: "0 0 16px", fontSize: 15, fontWeight: 700,
                                color: C.text }}>
                      Upload study material to begin
                    </p>

                    {/* Drop zone */}
                    <div
                      onDragOver={e => { e.preventDefault(); setDragging(true) }}
                      onDragLeave={() => setDragging(false)}
                      onDrop={e => { e.preventDefault(); setDragging(false); handlePendingFiles(e.dataTransfer.files) }}
                      onClick={() => mainFileRef.current?.click()}
                      style={{
                        border: `2px dashed ${dragging ? C.accent : C.border}`,
                        borderRadius: 10, padding: "20px 16px", textAlign: "center",
                        background: dragging ? "#1a1a2e" : C.surfaceAlt,
                        cursor: "pointer", transition: "all 0.2s", marginBottom: 12
                      }}
                    >
                      <p style={{ color: C.textSoft, fontSize: 13, margin: 0 }}>
                        📄 Drag & drop PDFs or TXT files here
                      </p>
                      <p style={{ color: C.muted, fontSize: 11, margin: "4px 0 0" }}>
                        or click to browse
                      </p>
                      <input ref={mainFileRef} type="file" multiple accept=".pdf,.txt"
                             style={{ display: "none" }} onChange={e => handlePendingFiles(e.target.files)} />
                    </div>

                    {/* File list */}
                    {pendingFiles.map((f, i) => (
                      <div key={i} style={{
                        display: "flex", justifyContent: "space-between", alignItems: "center",
                        padding: "6px 10px", borderRadius: 7, marginBottom: 5,
                        background: C.surfaceAlt, border: `1px solid ${C.border}`
                      }}>
                        <span style={{ color: C.text, fontSize: 12 }}>📎 {f.name}</span>
                        <button onClick={() => setPendingFiles(prev => prev.filter((_, j) => j !== i))}
                          style={{ background: "none", border: "none", color: C.muted,
                                   cursor: "pointer", fontSize: 15 }}>x</button>
                      </div>
                    ))}

                    {uploadMsg && (
                      <p style={{ color: C.teal, fontSize: 12, margin: "6px 0 10px" }}>{uploadMsg}</p>
                    )}

                    <button
                      onClick={startSession}
                      disabled={uploading || !pendingFiles.length}
                      style={{
                        width: "100%", marginTop: 4, padding: "10px 0",
                        borderRadius: 9, border: "none",
                        background: !pendingFiles.length || uploading
                          ? "#2a3a5c"
                          : `linear-gradient(135deg, ${C.accent}, #c0392b)`,
                        color: !pendingFiles.length || uploading ? C.muted : "white",
                        fontSize: 13, fontWeight: 700,
                        cursor: !pendingFiles.length || uploading ? "not-allowed" : "pointer"
                      }}
                    >
                      {uploading ? "Setting up..." : "Start Session"}
                    </button>
                  </div>
                </div>
              )}

              {/* ── Active session: messages ── */}
              {sessionId && messages.length === 0 && (
                <div style={{
                  display: "flex", flexDirection: "column", alignItems: "center",
                  justifyContent: "center", height: "100%",
                  textAlign: "center", gap: 10, padding: "60px 24px"
                }}>
                  <div style={{ fontSize: 44 }}>🧠</div>
                  <p style={{ color: C.text, fontSize: 16, fontWeight: 600, margin: 0 }}>
                    Ready to learn?
                  </p>
                  <p style={{ color: C.muted, fontSize: 13, margin: 0,
                               lineHeight: 1.6, maxWidth: 320 }}>
                    Share what you think you know about the material. The tutor will guide you deeper with questions.
                  </p>
                </div>
              )}

              {sessionId && messages.length > 0 && (
                messages.map((msg, i) => <Message key={i} msg={msg} />)
              )}

              {loading && (
                <div style={{ display: "flex", gap: 5, padding: "8px 4px", alignItems: "center" }}>
                  {[0, 1, 2].map(i => (
                    <div key={i} style={{
                      width: 7, height: 7, borderRadius: "50%",
                      background: C.teal, opacity: 0.7,
                      animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`
                    }} />
                  ))}
                  <span style={{ color: C.muted, fontSize: 12, marginLeft: 4 }}>Thinking...</span>
                </div>
              )}
              <div ref={bottomRef} />
            </div>

            {/* Input — only when session is active */}
            {sessionId && <div style={{ borderTop: `1px solid ${C.border}`, padding: "14px 20px",
                          background: C.surfaceAlt, display: "flex", gap: 10, alignItems: "center" }}>
              <input
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={e => e.key === "Enter" && !e.shiftKey && sendMessage()}
                placeholder="Share what you think you know..."
                disabled={loading}
                style={{
                  flex: 1, padding: "10px 14px", borderRadius: 10,
                  border: `1px solid ${C.border}`,
                  background: C.surface, color: C.text,
                  fontSize: 14, fontFamily: "sans-serif", outline: "none",
                  transition: "border-color 0.2s"
                }}
                onFocus={e => e.target.style.borderColor = C.accent}
                onBlur={e  => e.target.style.borderColor = C.border}
              />
              <button
                onClick={sendMessage}
                disabled={loading || !input.trim()}
                style={{
                  padding: "10px 20px", borderRadius: 10, border: "none",
                  background: loading || !input.trim()
                    ? "#2a3a5c"
                    : `linear-gradient(135deg, ${C.accent}, #c0392b)`,
                  color: loading || !input.trim() ? C.muted : "white",
                  fontSize: 14, fontWeight: 600, fontFamily: "sans-serif",
                  cursor: loading || !input.trim() ? "not-allowed" : "pointer",
                  whiteSpace: "nowrap"
                }}
              >
                {loading ? "..." : "Send"}
              </button>
            </div>}
          </div>
        )}
      </div>

      <style>{`
        @keyframes bounce {
          0%, 80%, 100% { transform: translateY(0); }
          40%           { transform: translateY(-6px); }
        }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: transparent; }
        ::-webkit-scrollbar-thumb { background: #2a3a5c; border-radius: 2px; }
      `}</style>
    </div>
  )
}