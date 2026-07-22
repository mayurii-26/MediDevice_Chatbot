import { useState, useCallback, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  MessageCircle, X, Minus, Copy, ThumbsUp, ThumbsDown,
  RotateCcw, Check, ChevronDown, Send, History,
} from "lucide-react";
import { useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneLight } from "react-syntax-highlighter/dist/esm/styles/prism";
import { useAuth } from "../context/AuthContext";
import SuggestedQuestions from "./SuggestedQuestions";
import CategoryDropdown from "./CategoryDropdown";
import VoiceInput from "./VoiceInput";
import DownloadModal from "./DownloadModal";
import ContactForm from "./ContactForm";
import { isPurchaseIntent, PURCHASE_INTENT_REPLY } from "../lib/purchaseIntentDetector";
import { isOutOfScope, OUT_OF_SCOPE_REPLY } from "../lib/outOfScopeDetector";
import { isSampleReportIntent, SAMPLE_REPORT_REPLY } from "../lib/sampleReportDetector";

const API_BASE_URL = "http://127.0.0.1:8000";
const FALLBACK_MESSAGE =
  "I'm a medical device assistant. Please ask about supported medical devices.";

// ── Design tokens (match website) ────────────────────────────────────────
const C = {
  navy:      "#1e3a5f",
  sky:       "#0ea5e9",
  skyLight:  "#e0f2fe",
  skyMid:    "#bae6fd",
  bg:        "#f8fafc",
  bgWarm:    "#f1f5f9",
  border:    "#e2e8f0",
  textMain:  "#1e3a5f",
  textMuted: "#64748b",
  textFaint: "#94a3b8",
  white:     "#ffffff",
  green:     "#22c55e",
  red:       "#ef4444",
  amber:     "#f59e0b",
};

// ── Markdown renderer ────────────────────────────────────────────────────
// All elements use a consistent base of 0.845rem (matches the message bubble).
// Headings are scaled relative to that base so responses never look different
// regardless of whether they come from cache, Gemini, or the refiner.
const FONT_BASE = "0.845rem";
const MD = {
  code({ node, inline, className, children, ...props }) {
    const match = /language-(\w+)/.exec(className || "");
    if (!inline && match) {
      return (
        <SyntaxHighlighter
          style={oneLight}
          language={match[1]}
          PreTag="div"
          customStyle={{ borderRadius: 8, fontSize: "0.78rem", margin: "6px 0", border: `1px solid ${C.border}` }}
          {...props}
        >
          {String(children).replace(/\n$/, "")}
        </SyntaxHighlighter>
      );
    }
    return (
      <code style={{
        background: C.bgWarm, padding: "2px 5px", borderRadius: 4,
        fontSize: "0.82em", fontFamily: "monospace", color: C.navy,
      }} {...props}>{children}</code>
    );
  },
  h1: ({ children }) => <p style={{ margin: "6px 0 3px", fontSize: "1rem",     fontWeight: 800, color: C.navy, lineHeight: 1.4 }}>{children}</p>,
  h2: ({ children }) => <p style={{ margin: "5px 0 3px", fontSize: "0.96rem",  fontWeight: 800, color: C.navy, lineHeight: 1.4 }}>{children}</p>,
  h3: ({ children }) => <p style={{ margin: "5px 0 2px", fontSize: "0.92rem",  fontWeight: 700, color: C.navy, lineHeight: 1.4 }}>{children}</p>,
  h4: ({ children }) => <p style={{ margin: "4px 0 2px", fontSize: FONT_BASE,  fontWeight: 700, color: C.navy, lineHeight: 1.4 }}>{children}</p>,
  h5: ({ children }) => <p style={{ margin: "4px 0 2px", fontSize: FONT_BASE,  fontWeight: 700, color: C.textMuted, lineHeight: 1.4 }}>{children}</p>,
  h6: ({ children }) => <p style={{ margin: "4px 0 2px", fontSize: FONT_BASE,  fontWeight: 600, color: C.textMuted, lineHeight: 1.4 }}>{children}</p>,
  table: ({ children }) => (
    <div style={{ overflowX: "auto", margin: "6px 0" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", fontSize: FONT_BASE }}>
        {children}
      </table>
    </div>
  ),
  th: ({ children }) => (
    <th style={{ background: C.skyLight, color: C.navy, padding: "5px 9px",
      border: `1px solid ${C.skyMid}`, fontWeight: 700, textAlign: "left",
      fontSize: FONT_BASE,
      whiteSpace: "normal", overflowWrap: "anywhere", wordBreak: "break-word",
      minWidth: 60, maxWidth: 200 }}>
      {children}
    </th>
  ),
  td: ({ children }) => (
    <td style={{ padding: "4px 9px", border: `1px solid ${C.border}`, color: "#374151",
      verticalAlign: "top", fontSize: FONT_BASE,
      whiteSpace: "normal", overflowWrap: "anywhere",
      wordBreak: "break-word", maxWidth: 220 }}>
      {children}
    </td>
  ),
  tr: ({ children }) => <tr>{children}</tr>,
  p:  ({ children }) => <p  style={{ margin: "3px 0", fontSize: FONT_BASE, lineHeight: 1.6 }}>{children}</p>,
  ul: ({ children }) => <ul style={{ paddingLeft: 16, margin: "3px 0", fontSize: FONT_BASE, lineHeight: 1.7 }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ paddingLeft: 16, margin: "3px 0", fontSize: FONT_BASE, lineHeight: 1.7 }}>{children}</ol>,
  li: ({ children }) => <li style={{ marginBottom: 2, fontSize: FONT_BASE }}>{children}</li>,
  strong: ({ children }) => <strong style={{ fontWeight: 700, color: C.navy }}>{children}</strong>,
  blockquote: ({ children }) => (
    <blockquote style={{ borderLeft: `3px solid ${C.sky}`, paddingLeft: 10,
      margin: "5px 0", color: C.textMuted, fontStyle: "italic", fontSize: FONT_BASE }}>
      {children}
    </blockquote>
  ),
};

// ── Helpers ───────────────────────────────────────────────────────────────
function formatTime(date) {
  return (date instanceof Date ? date : new Date(date))
    .toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function getGreeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

// ── User preferences hook ────────────────────────────────────────────────
function useUserPreferences(user, authHeaders) {
  const [prefs, setPrefs] = useState(null);

  useEffect(() => {
    if (!user?.id) { setPrefs(null); return; }
    authHeaders().then(async headers => {
      try {
        const { default: axios } = await import("axios");
        const r = await axios.get(`${API_BASE_URL}/preferences/${user.id}`, { headers });
        setPrefs(r.data);
      } catch { setPrefs(null); }
    });
  }, [user?.id]); // eslint-disable-line

  const savePrefs = useCallback(async (updates) => {
    if (!user?.id) return;
    try {
      const { default: axios } = await import("axios");
      const headers = await authHeaders();
      const res = await axios.post(`${API_BASE_URL}/preferences/${user.id}`, updates, { headers });
      setPrefs(res.data);
    } catch {}
  }, [user?.id, authHeaders]);

  return { prefs, savePrefs };
}

// ── ContactFormInline (for purchase intent) ──────────────────────────────
function ContactFormInline({ contactFormType = "general" }) {
  const [name, setName]     = useState("");
  const [email, setEmail]   = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState(null); // "success" | "error" | "fill"
  const [submitting, setSubmitting] = useState(false);

  // Determine reason and submission_type based on which form was opened
  const _typeMap = {
    pricing: { reason: "Pricing / Purchase", submission_type: "Pricing Inquiry" },
    sample:  { reason: "Sample Report",      submission_type: "Sample Report Request" },
    general: { reason: "General Support",    submission_type: "General Inquiry" },
  };
  const { reason, submission_type } = _typeMap[contactFormType] || _typeMap.general;

  const submitForm = async () => {
    if (!name.trim() || !email.trim() || !message.trim()) {
      setStatus("fill");
      return;
    }

    setSubmitting(true);
    setStatus(null);

    try {
      const { default: axios } = await import("axios");
      await axios.post(`${API_BASE_URL}/contact`, {
        name,
        email,
        message,
        reason,
        submission_type,
      });

      setStatus("success");
      setName("");
      setEmail("");
      setMessage("");
    } catch {
      setStatus("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div>
      {/* Name */}
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontWeight: 600, color: "#374151",
          fontSize: "0.8rem", marginBottom: 5 }}>Your Name</label>
        <input
          type="text"
          placeholder="Dr. Rajesh Kumar"
          value={name}
          onChange={e => setName(e.target.value)}
          style={{
            width: "100%", padding: "9px 11px", borderRadius: 8,
            border: `1.5px solid ${C.border}`, fontSize: "0.85rem",
            fontFamily: "inherit", background: C.bg,
            color: C.textMain, outline: "none", boxSizing: "border-box",
          }}
        />
      </div>

      {/* Email */}
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontWeight: 600, color: "#374151",
          fontSize: "0.8rem", marginBottom: 5 }}>Email Address</label>
        <input
          type="email"
          placeholder="rajesh@hospital.com"
          value={email}
          onChange={e => setEmail(e.target.value)}
          style={{
            width: "100%", padding: "9px 11px", borderRadius: 8,
            border: `1.5px solid ${C.border}`, fontSize: "0.85rem",
            fontFamily: "inherit", background: C.bg,
            color: C.textMain, outline: "none", boxSizing: "border-box",
          }}
        />
      </div>

      {/* Message */}
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "block", fontWeight: 600, color: "#374151",
          fontSize: "0.8rem", marginBottom: 5 }}>Message</label>
        <textarea
          rows={4}
          placeholder="Describe your pricing query, demo request, or purchase interest..."
          value={message}
          onChange={e => setMessage(e.target.value)}
          style={{
            width: "100%", padding: "9px 11px", borderRadius: 8,
            border: `1.5px solid ${C.border}`, fontSize: "0.85rem",
            fontFamily: "inherit", resize: "vertical", background: C.bg,
            color: C.textMain, outline: "none", boxSizing: "border-box",
          }}
        />
      </div>

      {/* Status messages */}
      {status === "success" && (
        <div style={{ background: "#f0fdf4", color: "#15803d", padding: "9px 12px",
          borderRadius: 8, fontSize: "0.8rem", fontWeight: 600, marginBottom: 12 }}>
          ✅ Query submitted successfully. We'll get back to you shortly!
        </div>
      )}
      {status === "error" && (
        <div style={{ background: "#fef2f2", color: "#dc2626", padding: "9px 12px",
          borderRadius: 8, fontSize: "0.8rem", fontWeight: 600, marginBottom: 12 }}>
          ❌ Failed to send. Please try again or email support@medideviceai.com
        </div>
      )}
      {status === "fill" && (
        <div style={{ background: "#fff5f5", color: "#f59e0b", padding: "9px 12px",
          borderRadius: 8, fontSize: "0.8rem", fontWeight: 600, marginBottom: 12 }}>
          ⚠️ Please fill in all fields before submitting.
        </div>
      )}

      {/* Submit button */}
      <button
        onClick={submitForm}
        disabled={submitting}
        style={{
          width: "100%", padding: "11px 0", borderRadius: 9, border: "none",
          background: submitting ? "#93c5fd" : C.sky,
          color: "#fff", fontWeight: 700, fontSize: "0.9rem",
          cursor: submitting ? "not-allowed" : "pointer",
          boxShadow: submitting ? "none" : "0 2px 8px rgba(14,165,233,0.28)",
          transition: "all 0.18s",
          fontFamily: "inherit",
        }}
      >
        {submitting ? "Sending..." : "Submit Query"}
      </button>
    </div>
  );
}


// ── ChatWidget ────────────────────────────────────────────────────────────
function ChatWidget({ onClose, onMinimize }) {
  const { user, isGuest, guestId }        = useAuth();
  const [question, setQuestion]           = useState("");
  const [messages, setMessages]           = useState([]);
  const [loading, setLoading]             = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [activeCategory, setActiveCategory] = useState(null);
  const [conversations, setConvs]         = useState([]);
  const [activeConvId, setActiveConvId]   = useState(null);
  const [pdfUrl, setPdfUrl]               = useState(null);
  const [showHistory, setShowHistory]     = useState(false);
  const [downloadDoc, setDownloadDoc]     = useState(null);
  const [copiedIndex, setCopiedIndex]     = useState(null);
  const [feedbackIndex, setFeedbackIndex] = useState({}); // {idx: "like"|"dislike"}
  const [showContactForm, setShowContactForm] = useState(false); // purchase intent popup
  const [contactFormType, setContactFormType] = useState("general"); // "pricing" | "sample" | "general"
  const guestMessagesRef                  = useRef([]);
  const messagesEndRef                    = useRef(null);
  const abortControllerRef               = useRef(null);
  const navigate                          = useNavigate();

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading, streamingText]);

  const authHeaders = useCallback(async () => {
    const { supabase } = await import("../lib/supabase");
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const { prefs, savePrefs } = useUserPreferences(user, authHeaders);

  // Preserve guest messages on login
  const prevUserIdRef = useRef(null);
  useEffect(() => {
    if (!user?.id || user.id === prevUserIdRef.current) return;
    prevUserIdRef.current = user.id;
    if (guestMessagesRef.current.length > 0) {
      setMessages(guestMessagesRef.current);
      guestMessagesRef.current = [];
    }
  }, [user?.id]);

  useEffect(() => {
    if (isGuest) guestMessagesRef.current = messages;
  }, [isGuest, messages]);

  useEffect(() => {
    if (prefs?.preferred_category && !activeCategory)
      setActiveCategory(prefs.preferred_category);
  }, [prefs]); // eslint-disable-line

  const loadConversations = useCallback(async () => {
    if (!user?.id) return;
    try {
      const { default: axios } = await import("axios");
      const headers = await authHeaders();
      const res = await axios.get(`${API_BASE_URL}/history/${user.id}`, { headers });
      setConvs(res.data || []);
    } catch { setConvs([]); }
  }, [authHeaders, user?.id]);

  useEffect(() => { loadConversations(); }, [loadConversations]);

  const loadConversation = async (id) => {
    if (!user?.id) return;
    setActiveConvId(id);
    setLoading(true);
    try {
      const { default: axios } = await import("axios");
      const headers = await authHeaders();
      const res = await axios.get(`${API_BASE_URL}/conversation/${id}`, { headers });
      setMessages((res.data || []).map(m => ({
        type: m.sender === "user" ? "user" : "bot",
        text: m.content,
        timestamp: m.created_at ? new Date(m.created_at) : new Date(),
      })));
    } catch {} finally { setLoading(false); setShowHistory(false); }
  };

  // ── Streaming ask ────────────────────────────────────────────────────
  const askQuestion = async (isRegenerate = false) => {
    const q = isRegenerate
      ? messages.filter(m => m.type === "user").at(-1)?.text
      : question.trim();
    if (!q) return;

    // ── Purchase / price / quote intent — short-circuit BEFORE retrieval ──
    if (isPurchaseIntent(q)) {
      // Show the user's message in the chat
      if (!isRegenerate) {
        setMessages(p => [...p, { type: "user", text: q, timestamp: new Date() }]);
        setQuestion("");
      }
      // Inject the canned bot reply
      setMessages(p => [...p, {
        type: "bot",
        text: PURCHASE_INTENT_REPLY,
        timestamp: new Date(),
        isPurchaseIntent: true,
      }]);
      return; // Do NOT proceed to FAISS / BM25 / Gemini / stream
    }
    // ─────────────────────────────────────────────────────────────────────

    // ── Sample Report Request intent — short-circuit BEFORE retrieval ────
    // Any request for sample/example ECG reports, PDF samples, etc.
    // returns a canned reply with a "Fill Contact Form" button.
    if (isSampleReportIntent(q)) {
      if (!isRegenerate) {
        setMessages(p => [...p, { type: "user", text: q, timestamp: new Date() }]);
        setQuestion("");
      }
      setMessages(p => [...p, {
        type: "bot",
        text: SAMPLE_REPORT_REPLY,
        timestamp: new Date(),
        isSampleReportIntent: true,
      }]);
      return; // Do NOT proceed to FAISS / BM25 / Gemini / stream
    }
    // ─────────────────────────────────────────────────────────────────────

    // ── Out-of-scope query guard — short-circuit BEFORE retrieval ────────
    if (isOutOfScope(q)) {
      if (!isRegenerate) {
        setMessages(p => [...p, { type: "user", text: q, timestamp: new Date() }]);
        setQuestion("");
      }
      setMessages(p => [...p, {
        type: "bot",
        text: OUT_OF_SCOPE_REPLY,
        timestamp: new Date(),
        isOutOfScope: true,
      }]);
      return; // Do NOT proceed to FAISS / BM25 / Gemini / stream
    }
    // ─────────────────────────────────────────────────────────────────────

    if (abortControllerRef.current) abortControllerRef.current.abort();
    abortControllerRef.current = new AbortController();

    if (isRegenerate) {
      setMessages(prev => prev.slice(0, -1));
    } else {
      setMessages(p => [...p, { type: "user", text: q, timestamp: new Date() }]);
      setQuestion("");
    }

    setLoading(true);
    setStreamingText("");

    try {
      const headers = await authHeaders();
      const response = await fetch(`${API_BASE_URL}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json", ...headers },
        body: JSON.stringify({
          question: q,
          user_id: user?.id || null,
          conversation_id: isGuest ? null : activeConvId,
        }),
        signal: abortControllerRef.current.signal,
      });

      if (!response.ok) throw new Error("Stream request failed");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullText = "";
      let meta = null;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          // Slice off "data: " prefix.
          const data = line.slice(6);
          if (!data) continue;
          const trimmed = data.trim();
          if (!trimmed) continue;
          if (trimmed.startsWith("[META]")) {
            try { meta = JSON.parse(trimmed.slice(6)); } catch {}
          } else if (trimmed.startsWith("[ERROR]")) {
            throw new Error(trimmed.slice(7).trim());
          } else {
            // Decode SSE-encoded newlines back to real newlines.
            // The backend encodes \n → \\n so that SSE line boundaries
            // are never confused with markdown paragraph breaks.
            // Without this decode: "PageWriter TC50CardiologyOverview..."
            // With this decode:    correct spacing between every section.
            const decoded = data.replace(/\\n/g, "\n");
            fullText += decoded;
            setStreamingText(fullText);
          }
        }
      }

      setLoading(false);
      setStreamingText("");
      if (meta?.conversation_id && !isGuest) setActiveConvId(meta.conversation_id);
      if (!isGuest && meta?.matched_category && meta.matched_category !== "Unknown")
        savePrefs({ preferred_category: meta.matched_category });

      setMessages(p => [...p, {
        type: "bot",
        text: fullText || FALLBACK_MESSAGE,
        timestamp: new Date(),
        source: meta?.source,
        product: meta?.matched_product,
        category: meta?.matched_category,
        confidence: meta?.confidence,
        documents: meta?.documents || [],
      }]);

      if (user?.id) loadConversations();
    } catch (err) {
      if (err.name === "AbortError") return;
      setLoading(false);
      setStreamingText("");
      setMessages(p => [...p, { type: "bot", text: err.message || FALLBACK_MESSAGE, timestamp: new Date() }]);
    }
  };

  const handleKey = e => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); askQuestion(); }
  };

  const handleCategoryChange = useCallback((cat) => {
    setActiveCategory(cat);
    if (!isGuest && cat) savePrefs({ preferred_category: cat });
  }, [isGuest, savePrefs]);

  const handleCopy = async (text, idx) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(idx);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch {}
  };

  const handleFeedback = (idx, type) => {
    setFeedbackIndex(prev => ({ ...prev, [idx]: type }));
  };

  const displayName = user?.email ? user.email.split("@")[0] : null;
  const initials    = user?.email ? user.email.slice(0, 2).toUpperCase() : null;


  return (
    <div style={{
      width: "100%", height: "100%", display: "flex", flexDirection: "column",
      fontFamily: "'Segoe UI', system-ui, Arial, sans-serif",
      background: C.bg,
    }}>

      {/* ── Header ── */}
      <div style={{
        background: `linear-gradient(135deg, ${C.navy}, ${C.sky})`,
        padding: "12px 16px", flexShrink: 0,
        display: "flex", alignItems: "center", justifyContent: "space-between",
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div style={{
            width: 34, height: 34, borderRadius: "50%",
            background: "rgba(255,255,255,0.18)",
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <MessageCircle size={17} color="#fff" />
          </div>
          <div>
            <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.92rem", letterSpacing: "-0.2px" }}>
              Medical AI Assistant
            </div>
            <div style={{ fontSize: "0.68rem", color: "#bfdbfe", marginTop: 1 }}>
              {isGuest ? "Guest session" : `Signed in as ${displayName}`}
            </div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 5, alignItems: "center" }}>
          {!isGuest && (
            <button onClick={() => setShowHistory(h => !h)}
              title="Chat history"
              style={{
                background: showHistory ? "rgba(255,255,255,0.3)" : "rgba(255,255,255,0.15)",
                border: "none", borderRadius: 7, padding: "6px 7px",
                color: "#fff", cursor: "pointer", display: "flex", alignItems: "center",
                transition: "background 0.15s",
              }}>
              <History size={15} />
            </button>
          )}
          {isGuest && (
            <button onClick={() => navigate("/login")}
              style={{
                background: "rgba(255,255,255,0.22)", border: "none",
                borderRadius: 7, padding: "5px 11px", color: "#fff",
                cursor: "pointer", fontSize: "0.76rem", fontWeight: 700,
              }}>
              Sign In
            </button>
          )}
          <button onClick={onMinimize}
            style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 7,
              padding: 6, color: "#fff", cursor: "pointer", display: "flex", alignItems: "center" }}>
            <Minus size={13} />
          </button>
          <button onClick={onClose}
            style={{ background: "rgba(255,255,255,0.15)", border: "none", borderRadius: 7,
              padding: 6, color: "#fff", cursor: "pointer", display: "flex", alignItems: "center" }}>
            <X size={13} />
          </button>
        </div>
      </div>

      {/* ── Guest banner ── */}
      {isGuest && (
        <div style={{
          background: "#fffbeb", borderBottom: `1px solid #fde68a`,
          padding: "7px 14px", fontSize: "0.76rem", color: "#92400e",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexShrink: 0,
        }}>
          <span>👤 Guest — conversations not saved</span>
          <button onClick={() => navigate("/login")}
            style={{ background: "none", border: "none", color: C.sky,
              cursor: "pointer", fontWeight: 700, fontSize: "0.76rem" }}>
            Sign in →
          </button>
        </div>
      )}

      {/* ── Preferred category banner (logged-in, empty chat) ── */}
      {!isGuest && prefs?.preferred_category && messages.length === 0 && (
        <div style={{
          background: "#f0f9ff", borderBottom: `1px solid ${C.skyMid}`,
          padding: "7px 14px", fontSize: "0.76rem", color: "#0369a1",
          display: "flex", justifyContent: "space-between", alignItems: "center",
          flexShrink: 0,
        }}>
          <span>⭐ Last browsed: <strong>{prefs.preferred_category}</strong></span>
          <button onClick={() => setActiveCategory(prefs.preferred_category)}
            style={{ background: "none", border: "none", color: C.sky,
              cursor: "pointer", fontWeight: 700, fontSize: "0.76rem" }}>
            Resume →
          </button>
        </div>
      )}

      {/* ── History panel ── */}
      <AnimatePresence>
        {showHistory && !isGuest && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }} transition={{ duration: 0.2 }}
            style={{ overflow: "hidden", background: C.white, borderBottom: `1px solid ${C.border}` }}>
            <div style={{ padding: "10px 12px", maxHeight: 160, overflowY: "auto" }}>
              <button onClick={() => { setMessages([]); setActiveConvId(null); setShowHistory(false); }}
                style={{
                  width: "100%", textAlign: "left", padding: "8px 10px",
                  background: C.sky, color: C.white, border: "none",
                  borderRadius: 7, cursor: "pointer", fontWeight: 700,
                  fontSize: "0.8rem", marginBottom: 6,
                }}>
                + New Chat
              </button>
              {conversations.length === 0
                ? <p style={{ color: C.textFaint, fontSize: "0.78rem", padding: "4px 0" }}>
                    No conversations yet.
                  </p>
                : conversations.map(c => (
                  <button key={c.id} onClick={() => loadConversation(c.id)}
                    style={{
                      width: "100%", textAlign: "left", padding: "7px 10px",
                      background: c.id === activeConvId ? C.skyLight : "transparent",
                      color: C.navy, border: "none", borderRadius: 6,
                      cursor: "pointer", fontSize: "0.8rem", marginBottom: 2,
                      whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                    }}>
                    {c.title}
                  </button>
                ))
              }
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Messages ── */}
      <div style={{
        flex: 1, overflowY: "auto", padding: "14px 14px 6px",
        display: "flex", flexDirection: "column", gap: 10,
        background: C.bg,
      }}>
        {/* Welcome state */}
        {messages.length === 0 && (
          <div style={{
            textAlign: "center", marginTop: 28,
            padding: "0 8px",
          }}>
            <div style={{
              width: 52, height: 52, borderRadius: "50%",
              background: `linear-gradient(135deg, ${C.navy}, ${C.sky})`,
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 14px",
              boxShadow: "0 4px 16px rgba(14,165,233,0.25)",
            }}>
              <MessageCircle size={24} color="#fff" />
            </div>
            <div style={{ fontWeight: 800, color: C.navy, fontSize: "1rem", marginBottom: 5 }}>
              {!isGuest
                ? `${getGreeting()}, ${displayName}!`
                : "How can I help you?"}
            </div>
            <div style={{ color: C.textMuted, fontSize: "0.83rem", lineHeight: 1.6, maxWidth: 280, margin: "0 auto" }}>
              {!isGuest
                ? "Ask me anything about medical devices — specs, features, or comparisons."
                : "Ask about medical devices. Sign in to save your conversations."}
            </div>
          </div>
        )}

        {/* Message bubbles */}
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: "flex", flexDirection: "column",
            alignItems: msg.type === "user" ? "flex-end" : "flex-start",
          }}>
            {/* Bubble */}
            <div style={{
              maxWidth: "86%", padding: "9px 13px", borderRadius: 14,
              fontSize: "0.845rem", lineHeight: 1.58,
              background: msg.type === "user"
                ? `linear-gradient(135deg, ${C.navy}, ${C.sky})`
                : C.white,
              color: msg.type === "user" ? "#fff" : C.textMain,
              borderBottomRightRadius: msg.type === "user" ? 3 : 14,
              borderBottomLeftRadius:  msg.type === "bot"  ? 3 : 14,
              boxShadow: msg.type === "user"
                ? "0 2px 10px rgba(14,165,233,0.22)"
                : "0 1px 4px rgba(30,58,95,0.08)",
              border: msg.type === "bot" ? `1px solid ${C.border}` : "none",
              overflowWrap: "break-word",
              wordBreak: "break-word",
              minWidth: 0,
              overflowX: "hidden",
            }}>
              {/* Source badge */}
              {msg.type === "bot" && msg.source && (
                <div style={{ marginBottom: 6, display: "flex", flexWrap: "wrap", gap: 4 }}>
                  <span style={{
                    fontSize: "0.66rem", fontWeight: 700,
                    padding: "2px 7px", borderRadius: 20,
                    background: C.skyLight, color: C.sky,
                  }}>
                    {msg.source === "faiss"          ? "📦 Knowledge Base"
                     : msg.source === "dynamic_search" ? "🌐 Web"
                     : msg.source === "cache"          ? "⚡ Cached"
                     :                                   "⚠️ Fallback"}
                  </span>
                  {msg.product && (
                    <span style={{ fontSize: "0.66rem", padding: "2px 7px",
                      borderRadius: 20, background: C.bgWarm, color: "#374151" }}>
                      📌 {msg.product}
                    </span>
                  )}
                </div>
              )}

              {/* Content */}
              {msg.type === "bot"
                ? <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{msg.text}</ReactMarkdown>
                : <span>{msg.text}</span>
              }

              {/* ── Persistent contact button for purchase intent messages ── */}
              {msg.type === "bot" && msg.isPurchaseIntent && (
                <div style={{ marginTop: 10 }}>
                  <button
                    onClick={() => { setContactFormType("pricing"); setShowContactForm(true); }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "8px 14px",
                      borderRadius: 8,
                      border: `1.5px solid ${C.sky}`,
                      background: C.skyLight,
                      color: C.sky,
                      fontWeight: 700,
                      fontSize: "0.82rem",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s, transform 0.1s",
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = C.skyMid;
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = C.skyLight;
                      e.currentTarget.style.transform = "none";
                    }}
                  >
                    📩 Fill Contact Form
                  </button>
                </div>
              )}
              {/* ─────────────────────────────────────────────────────────── */}

              {/* ── Persistent contact button for sample report intent messages ── */}
              {msg.type === "bot" && msg.isSampleReportIntent && (
                <div style={{ marginTop: 10 }}>
                  <button
                    onClick={() => { setContactFormType("sample"); setShowContactForm(true); }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "8px 14px",
                      borderRadius: 8,
                      border: `1.5px solid ${C.sky}`,
                      background: C.skyLight,
                      color: C.sky,
                      fontWeight: 700,
                      fontSize: "0.82rem",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s, transform 0.1s",
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = C.skyMid;
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = C.skyLight;
                      e.currentTarget.style.transform = "none";
                    }}
                  >
                    📩 Fill Contact Form
                  </button>
                </div>
              )}
              {/* ──────────────────────────────────────────────────────────────── */}

              {/* ── Persistent contact button for out-of-scope messages ── */}
              {msg.type === "bot" && msg.isOutOfScope && (
                <div style={{ marginTop: 10 }}>
                  <button
                    onClick={() => { setContactFormType("general"); setShowContactForm(true); }}
                    style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 7,
                      padding: "8px 14px",
                      borderRadius: 8,
                      border: `1.5px solid ${C.sky}`,
                      background: C.skyLight,
                      color: C.sky,
                      fontWeight: 700,
                      fontSize: "0.82rem",
                      cursor: "pointer",
                      fontFamily: "inherit",
                      transition: "background 0.15s, transform 0.1s",
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = C.skyMid;
                      e.currentTarget.style.transform = "translateY(-1px)";
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = C.skyLight;
                      e.currentTarget.style.transform = "none";
                    }}
                  >
                    📋 Contact Support
                  </button>
                </div>
              )}
              {/* ──────────────────────────────────────────────────────── */}

              {/* Document cards */}
              {msg.type === "bot" && msg.documents?.length > 0 && (
                <div style={{ marginTop: 8, borderTop: `1px solid ${C.border}`, paddingTop: 8 }}>
                  <div style={{
                    fontSize: "0.68rem", fontWeight: 700, color: C.sky,
                    textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 6,
                  }}>
                    📄 Documents
                  </div>
                  {msg.documents.map(doc => (
                    <div key={doc.id} style={{
                      display: "flex", justifyContent: "space-between", alignItems: "center",
                      padding: "5px 0", borderBottom: `1px solid ${C.bgWarm}`, gap: 8,
                    }}>
                      <span style={{ fontSize: "0.76rem", color: C.navy, fontWeight: 600,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", flex: 1 }}>
                        {doc.document_name}
                      </span>
                      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
                        <button onClick={() => setPdfUrl(doc.file_url)}
                          style={{ padding: "3px 8px", borderRadius: 5, background: C.skyLight,
                            color: C.sky, border: "none", cursor: "pointer", fontSize: "0.7rem", fontWeight: 600 }}>
                          View
                        </button>
                        <button onClick={() => setDownloadDoc(doc)}
                          style={{ padding: "3px 8px", borderRadius: 5, background: "#f0fdf4",
                            color: "#15803d", border: "none", cursor: "pointer", fontSize: "0.7rem", fontWeight: 600 }}>
                          ⬇
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Timestamp + action row */}
            <div style={{
              display: "flex", alignItems: "center", gap: 5, marginTop: 3,
              flexDirection: msg.type === "user" ? "row-reverse" : "row",
              paddingLeft: msg.type === "bot" ? 2 : 0,
              paddingRight: msg.type === "user" ? 2 : 0,
            }}>
              {msg.timestamp && (
                <span style={{ fontSize: "0.65rem", color: C.textFaint }}>
                  {formatTime(msg.timestamp)}
                </span>
              )}
              {msg.type === "bot" && (
                <div style={{ display: "flex", gap: 2 }}>
                  {/* Copy */}
                  <button onClick={() => handleCopy(msg.text, i)} title="Copy"
                    style={{ background: "none", border: "none", cursor: "pointer",
                      padding: "2px 3px", borderRadius: 4, color: copiedIndex === i ? C.green : C.textFaint,
                      display: "flex", alignItems: "center" }}>
                    {copiedIndex === i ? <Check size={12} /> : <Copy size={12} />}
                  </button>
                  {/* Like */}
                  <button onClick={() => handleFeedback(i, "like")} title="Good response"
                    style={{ background: "none", border: "none", cursor: "pointer",
                      padding: "2px 3px", borderRadius: 4,
                      color: feedbackIndex[i] === "like" ? C.green : C.textFaint,
                      display: "flex", alignItems: "center" }}>
                    <ThumbsUp size={12} />
                  </button>
                  {/* Dislike */}
                  <button onClick={() => handleFeedback(i, "dislike")} title="Poor response"
                    style={{ background: "none", border: "none", cursor: "pointer",
                      padding: "2px 3px", borderRadius: 4,
                      color: feedbackIndex[i] === "dislike" ? C.red : C.textFaint,
                      display: "flex", alignItems: "center" }}>
                    <ThumbsDown size={12} />
                  </button>
                  {/* Regenerate — last bot message only */}
                  {i === messages.length - 1 && messages.length >= 2 && !loading && (
                    <button onClick={() => askQuestion(true)} title="Regenerate"
                      style={{ background: "none", border: "none", cursor: "pointer",
                        padding: "2px 3px", borderRadius: 4, color: C.textFaint,
                        display: "flex", alignItems: "center" }}>
                      <RotateCcw size={12} />
                    </button>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Streaming bubble */}
        {loading && streamingText && (
          <div style={{ display: "flex", flexDirection: "column", alignItems: "flex-start" }}>
            <div style={{
              maxWidth: "86%", padding: "9px 13px", borderRadius: 14, borderBottomLeftRadius: 3,
              background: C.white, border: `1px solid ${C.border}`,
              boxShadow: "0 1px 4px rgba(30,58,95,0.08)",
              fontSize: "0.845rem", color: C.textMain, lineHeight: 1.58,
              overflowWrap: "break-word", wordBreak: "break-word",
              minWidth: 0, overflowX: "hidden",
            }}>
              <ReactMarkdown remarkPlugins={[remarkGfm]} components={MD}>{streamingText}</ReactMarkdown>
            </div>
          </div>
        )}

        {/* Thinking animation */}
        {loading && !streamingText && (
          <div style={{ display: "flex", alignItems: "flex-start" }}>
            <div style={{
              padding: "10px 14px", borderRadius: 14, borderBottomLeftRadius: 3,
              background: C.white, border: `1px solid ${C.border}`,
              boxShadow: "0 1px 4px rgba(30,58,95,0.08)",
              display: "flex", alignItems: "center", gap: 7,
            }}>
              <span style={{ fontSize: "0.76rem", color: C.textMuted }}>Thinking</span>
              <div style={{ display: "flex", gap: 3, alignItems: "center" }}>
                {[0, 0.18, 0.36].map((delay, di) => (
                  <motion.div key={di}
                    animate={{ y: [0, -4, 0] }}
                    transition={{ repeat: Infinity, duration: 0.65, delay, ease: "easeInOut" }}
                    style={{ width: 5, height: 5, borderRadius: "50%", background: C.sky }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>


      {/* ── Contact Support popup (purchase intent) ── */}
      <AnimatePresence>
        {showContactForm && (
          <motion.div
            key="contact-support-panel"
            initial={{ opacity: 0, y: 20, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 20, scale: 0.97 }}
            transition={{ duration: 0.22, ease: "easeOut" }}
            style={{
              position: "absolute",
              inset: 0,
              background: "rgba(0,0,0,0.45)",
              zIndex: 20,
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "flex-end",
              borderRadius: 16,
            }}
            onClick={() => setShowContactForm(false)}
          >
            <motion.div
              initial={{ y: "100%" }}
              animate={{ y: 0 }}
              exit={{ y: "100%" }}
              transition={{ duration: 0.26, ease: "easeOut" }}
              onClick={e => e.stopPropagation()}
              style={{
                width: "100%",
                background: C.white,
                borderRadius: "16px 16px 0 0",
                boxShadow: "0 -8px 40px rgba(30,58,95,0.18)",
                overflow: "hidden",
                maxHeight: "90%",
                display: "flex",
                flexDirection: "column",
              }}
            >
              {/* Panel header */}
              <div style={{
                background: `linear-gradient(135deg, ${C.navy}, ${C.sky})`,
                padding: "14px 16px",
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                flexShrink: 0,
              }}>
                <div>
                  <div style={{ fontWeight: 700, color: "#fff", fontSize: "0.95rem" }}>
                    📬 Contact Support
                  </div>
                  <div style={{ fontSize: "0.72rem", color: "#bfdbfe", marginTop: 2 }}>
                    Fill out the form and our support team will contact you shortly.
                  </div>
                </div>
                <button
                  onClick={() => setShowContactForm(false)}
                  style={{
                    background: "rgba(255,255,255,0.15)",
                    border: "none",
                    borderRadius: 7,
                    padding: "5px 7px",
                    color: "#fff",
                    cursor: "pointer",
                    display: "flex",
                    alignItems: "center",
                  }}
                  aria-label="Close contact form"
                >
                  <X size={14} />
                </button>
              </div>

              {/* Scrollable form body */}
              <div style={{ overflowY: "auto", padding: "18px 16px 20px", flex: 1 }}>
                <ContactFormInline contactFormType={contactFormType} />
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── Category + suggestions (compact, no nesting) ── */}
      <div style={{
        padding: "10px 12px 8px", background: C.white,
        borderTop: `1px solid ${C.border}`, flexShrink: 0,
      }}>
        <CategoryDropdown
          setQuestion={setQuestion}
          onCategoryChange={handleCategoryChange}
          defaultCategory={activeCategory}
        />
        <div style={{ marginTop: 7, maxHeight: 75, overflowY: "auto" }}>
          <SuggestedQuestions onSelect={setQuestion} activeCategory={activeCategory} />
        </div>
      </div>

      {/* ── Input row ── */}
      <div style={{
        padding: "9px 12px 12px", background: C.white,
        borderTop: `1px solid ${C.border}`, flexShrink: 0,
      }}>
        <div style={{ display: "flex", gap: 7, alignItems: "flex-end" }}>
          <textarea rows={2} value={question}
            onChange={e => setQuestion(e.target.value)}
            onKeyDown={handleKey}
            placeholder="Ask about medical devices…"
            style={{
              flex: 1, padding: "9px 11px", borderRadius: 9,
              border: `1.5px solid ${C.border}`, fontSize: "0.85rem",
              fontFamily: "inherit", resize: "none", background: C.bg,
              color: C.textMain, outline: "none", transition: "border-color 0.2s",
            }}
            onFocus={e => e.currentTarget.style.borderColor = C.sky}
            onBlur={e => e.currentTarget.style.borderColor = C.border}
          />
          <VoiceInput setQuestion={setQuestion} />
          <button onClick={() => askQuestion()} disabled={loading}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center",
              padding: "0 14px", height: 38, borderRadius: 9, border: "none",
              background: loading ? "#93b8d8" : C.sky,
              color: C.white, fontWeight: 700, fontSize: "0.84rem",
              cursor: loading ? "not-allowed" : "pointer",
              flexShrink: 0, transition: "all 0.15s",
              boxShadow: loading ? "none" : "0 2px 8px rgba(14,165,233,0.28)",
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.transform = "translateY(-1px)"; }}
            onMouseLeave={e => { e.currentTarget.style.transform = "none"; }}>
            {loading ? "…" : <><Send size={15} style={{ marginRight: 5 }} /> Ask</>}
          </button>
        </div>
      </div>

      {/* ── PDF viewer overlay ── */}
      {pdfUrl && (
        <div onClick={() => setPdfUrl(null)} style={{
          position: "absolute", inset: 0, background: "rgba(0,0,0,0.65)",
          display: "flex", alignItems: "center", justifyContent: "center",
          zIndex: 10, borderRadius: 16,
        }}>
          <div onClick={e => e.stopPropagation()} style={{
            background: C.white, borderRadius: 12, width: "95%", height: "90%",
            display: "flex", flexDirection: "column", overflow: "hidden",
            position: "relative", boxShadow: "0 20px 60px rgba(0,0,0,0.3)",
          }}>
            <button onClick={() => setPdfUrl(null)} style={{
              position: "absolute", top: 8, right: 10, background: C.bgWarm,
              border: "none", borderRadius: 7, width: 28, height: 28,
              cursor: "pointer", fontWeight: 700, color: "#374151",
              display: "flex", alignItems: "center", justifyContent: "center", zIndex: 11,
            }}>✕</button>
            <iframe src={`https://docs.google.com/viewer?embedded=true&url=${encodeURIComponent(pdfUrl)}`} title="PDF" style={{ flex: 1, border: "none" }} sandbox="allow-scripts allow-same-origin" />
          </div>
        </div>
      )}

      {/* ── Secure download modal ── */}
      <DownloadModal
        open={!!downloadDoc}
        onClose={() => setDownloadDoc(null)}
        document={downloadDoc}
        userId={user?.id || null}
        guestId={guestId || null}
      />
    </div>
  );
}


// ── FAB + window ──────────────────────────────────────────────────────────
export default function FloatingChatbot({ externalOpen, onExternalOpenHandled }) {
  const [open,      setOpen]      = useState(false);
  const [minimized, setMinimized] = useState(false);

  useEffect(() => {
    if (externalOpen) {
      setOpen(true); setMinimized(false);
      if (onExternalOpenHandled) onExternalOpenHandled();
    }
  }, [externalOpen, onExternalOpenHandled]);

  return (
    <>
      <AnimatePresence>
        {open && !minimized && (
          <motion.div key="chat-window"
            initial={{ opacity: 0, scale: 0.88, y: 18 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.88, y: 18 }}
            transition={{ type: "spring", stiffness: 340, damping: 28 }}
            style={{
              position: "fixed", bottom: 90, right: 24,
              width: 420, height: 680, background: C.white,
              borderRadius: 16,
              boxShadow: "0 20px 70px rgba(30,58,95,0.22)",
              zIndex: 1000, overflow: "hidden",
              display: "flex", flexDirection: "column",
              border: `1px solid ${C.border}`,
            }}
            className="float-chat-window">
            <ChatWidget onClose={() => setOpen(false)} onMinimize={() => setMinimized(true)} />
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && minimized && (
          <motion.div key="chat-bar"
            initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: 10 }}
            onClick={() => setMinimized(false)}
            style={{
              position: "fixed", bottom: 90, right: 24,
              background: `linear-gradient(135deg, ${C.navy}, ${C.sky})`,
              color: C.white, borderRadius: 12, padding: "11px 18px",
              cursor: "pointer", zIndex: 1000,
              display: "flex", alignItems: "center", gap: 9,
              boxShadow: "0 6px 24px rgba(14,165,233,0.35)",
              fontWeight: 700, fontSize: "0.88rem",
            }}>
            <MessageCircle size={16} />
            Medical AI Assistant
            <X size={13} onClick={e => { e.stopPropagation(); setOpen(false); setMinimized(false); }} />
          </motion.div>
        )}
      </AnimatePresence>

      <motion.button
        onClick={() => { setOpen(o => !o); setMinimized(false); }}
        whileHover={{ scale: 1.06 }} whileTap={{ scale: 0.96 }}
        style={{
          position: "fixed", bottom: 24, right: 24,
          width: 60, height: 60, borderRadius: "50%",
          background: `linear-gradient(135deg, ${C.navy}, ${C.sky})`,
          border: "none", cursor: "pointer",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 8px 28px rgba(14,165,233,0.42)",
          zIndex: 1001, color: C.white,
        }}
        aria-label="Open AI Assistant">
        <AnimatePresence mode="wait">
          {open
            ? <motion.span key="x" initial={{ rotate: -90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: 90, opacity: 0 }}
                transition={{ duration: 0.16 }}><X size={23} /></motion.span>
            : <motion.span key="chat" initial={{ rotate: 90, opacity: 0 }}
                animate={{ rotate: 0, opacity: 1 }} exit={{ rotate: -90, opacity: 0 }}
                transition={{ duration: 0.16 }}><MessageCircle size={23} /></motion.span>
          }
        </AnimatePresence>
      </motion.button>

      {!open && (
        <motion.div
          animate={{ scale: [1, 1.5], opacity: [0.4, 0] }}
          transition={{ repeat: Infinity, duration: 2.2, ease: "easeOut" }}
          style={{
            position: "fixed", bottom: 24, right: 24,
            width: 60, height: 60, borderRadius: "50%",
            background: C.sky, zIndex: 999, pointerEvents: "none",
          }}
        />
      )}

      <style>{`
        @media (max-width: 480px) {
          .float-chat-window {
            width: calc(100vw - 16px) !important;
            height: calc(100vh - 100px) !important;
            right: 8px !important; bottom: 80px !important;
            border-radius: 12px !important;
          }
        }
      `}</style>
    </>
  );
}
