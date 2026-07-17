/**
 * DownloadModal.jsx
 *
 * Two-step secure document download:
 *   Step 1 — Information form  (name, email, phone, designation, country)
 *   Step 2 — OTP verification  (6-digit code sent to email)
 *
 * After successful OTP verification the file URL is opened for download.
 *
 * Props:
 *   open          boolean          — whether the modal is visible
 *   onClose       () => void       — close callback
 *   document      { id, document_name, file_url, product_name }
 *   userId        string | null    — authenticated user ID (null = guest)
 *   guestId       string | null    — guest session ID (null = logged-in user)
 */

import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import { FileText, X, Mail, User, Phone, Briefcase, Globe, ArrowRight, Shield, RefreshCw, CheckCircle } from "lucide-react";

const API = "http://127.0.0.1:8000";

const COUNTRIES = [
  "India", "United States", "United Kingdom", "Canada", "Australia",
  "Germany", "France", "UAE", "Saudi Arabia", "Singapore", "Other",
];

const DESIGNATIONS = [
  "Biomedical Engineer", "Clinical Engineer", "Doctor / Physician",
  "Nurse / Healthcare Professional", "Hospital Administrator",
  "Medical Equipment Manager", "Researcher / Academic",
  "Sales / Business Development", "Student", "Other",
];

// ── Step 1: Info Form ─────────────────────────────────────────────────────
function InfoForm({ doc, userId, guestId, onSuccess, onBlockedError, onClose }) {
  const [form, setForm] = useState({
    full_name: "", email: "", phone: "",
    designation: "", country: "",
  });
  const [errors, setErrors]   = useState({});
  const [loading, setLoading] = useState(false);
  const [apiError, setApiError] = useState("");

  function validate() {
    const e = {};
    if (!form.full_name.trim())   e.full_name   = "Full name is required";
    if (!form.email.trim())       e.email       = "Email is required";
    else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email))
                                  e.email       = "Enter a valid email address";
    if (!form.phone.trim())       e.phone       = "Phone number is required";
    else if (!/^\+?[\d\s\-()]{7,15}$/.test(form.phone.trim()))
                                  e.phone       = "Enter a valid phone number";
    if (!form.designation)        e.designation = "Please select your designation";
    if (!form.country)            e.country     = "Please select your country";
    return e;
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setApiError("");
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }
    setErrors({});
    setLoading(true);
    try {
      const payload = {
        full_name:        form.full_name.trim(),
        email:            form.email.trim().toLowerCase(),
        phone:            form.phone.trim(),
        designation:      form.designation,
        country:          form.country,
        document_id:      String(doc.id),
        document_name:    doc.document_name,
        file_url:         doc.file_url,
        user_id:          userId || null,
        guest_session_id: guestId || null,
      };
      const res = await axios.post(`${API}/download/request`, payload);
      onSuccess({
        requestId: res.data.request_id,
        email:     res.data.email,
        fullName:  form.full_name.trim(),
      });
    } catch (err) {
      const detail = err.response?.data?.detail || "Failed to send OTP. Please try again.";
      // Route hard-block errors to dedicated screens; others stay inline
      if (
        detail.toLowerCase().includes("download limit") ||
        detail.toLowerCase().includes("sign in")
      ) {
        onBlockedError(detail);
      } else {
        setApiError(detail);
      }
    } finally {
      setLoading(false);
    }
  }

  function field(name, label, type = "text", Icon) {
    return (
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 700,
          color: "#374151", marginBottom: 5 }}>{label}</label>
        <div style={{ position: "relative" }}>
          {Icon && (
            <Icon size={15} color="#94a3b8" style={{
              position: "absolute", left: 12, top: "50%",
              transform: "translateY(-50%)", pointerEvents: "none",
            }} />
          )}
          <input
            type={type}
            value={form[name]}
            onChange={e => { setForm(p => ({ ...p, [name]: e.target.value })); setErrors(p => ({ ...p, [name]: "" })); }}
            placeholder={label}
            style={{
              width: "100%", padding: Icon ? "10px 12px 10px 34px" : "10px 12px",
              borderRadius: 8, boxSizing: "border-box",
              border: `1.5px solid ${errors[name] ? "#ef4444" : "#e2e8f0"}`,
              fontSize: "0.875rem", fontFamily: "inherit",
              background: "#f8fafc", color: "#1e3a5f", outline: "none",
              transition: "border-color 0.15s",
            }}
            onFocus={e => e.target.style.borderColor = errors[name] ? "#ef4444" : "#0ea5e9"}
            onBlur={e => e.target.style.borderColor = errors[name] ? "#ef4444" : "#e2e8f0"}
          />
        </div>
        {errors[name] && <p style={{ color: "#ef4444", fontSize: "0.75rem", margin: "4px 0 0" }}>{errors[name]}</p>}
      </div>
    );
  }

  function selectField(name, label, options, Icon) {
    return (
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 700,
          color: "#374151", marginBottom: 5 }}>{label}</label>
        <div style={{ position: "relative" }}>
          {Icon && (
            <Icon size={15} color="#94a3b8" style={{
              position: "absolute", left: 12, top: "50%",
              transform: "translateY(-50%)", pointerEvents: "none", zIndex: 1,
            }} />
          )}
          <select
            value={form[name]}
            onChange={e => { setForm(p => ({ ...p, [name]: e.target.value })); setErrors(p => ({ ...p, [name]: "" })); }}
            style={{
              width: "100%", padding: Icon ? "10px 12px 10px 34px" : "10px 12px",
              borderRadius: 8, boxSizing: "border-box", appearance: "none",
              border: `1.5px solid ${errors[name] ? "#ef4444" : "#e2e8f0"}`,
              fontSize: "0.875rem", fontFamily: "inherit",
              background: "#f8fafc", color: form[name] ? "#1e3a5f" : "#94a3b8",
              outline: "none", cursor: "pointer",
            }}
          >
            <option value="">Select {label}</option>
            {options.map(o => <option key={o} value={o}>{o}</option>)}
          </select>
        </div>
        {errors[name] && <p style={{ color: "#ef4444", fontSize: "0.75rem", margin: "4px 0 0" }}>{errors[name]}</p>}
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit}>
      {/* Document info banner */}
      <div style={{ background: "#f0f9ff", border: "1px solid #bae6fd",
        borderRadius: 10, padding: "12px 14px", marginBottom: 20,
        display: "flex", gap: 10, alignItems: "flex-start" }}>
        <FileText size={18} color="#0ea5e9" style={{ flexShrink: 0, marginTop: 2 }} />
        <div>
          <div style={{ fontWeight: 700, color: "#1e3a5f", fontSize: "0.9rem",
            lineHeight: 1.3 }}>{doc.document_name}</div>
          {doc.product_name && (
            <div style={{ fontSize: "0.78rem", color: "#64748b", marginTop: 3 }}>
              📌 {doc.product_name}
            </div>
          )}
        </div>
      </div>

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "0 14px" }}>
        <div style={{ gridColumn: "1 / -1" }}>{field("full_name", "Full Name", "text", User)}</div>
        <div style={{ gridColumn: "1 / -1" }}>{field("email", "Email Address", "email", Mail)}</div>
        {field("phone", "Phone Number", "tel", Phone)}
        {selectField("designation", "Designation", DESIGNATIONS, Briefcase)}
        <div style={{ gridColumn: "1 / -1" }}>{selectField("country", "Country", COUNTRIES, Globe)}</div>
      </div>

      {apiError && (
        <div style={{ background: "#fef2f2", border: "1px solid #fecaca",
          borderRadius: 8, padding: "10px 14px", marginBottom: 14,
          color: "#dc2626", fontSize: "0.82rem" }}>
          {apiError}
        </div>
      )}

      <p style={{ fontSize: "0.75rem", color: "#94a3b8", marginBottom: 14, lineHeight: 1.5 }}>
        By submitting, you agree that your information will be used to process
        this download request. A one-time verification code will be sent to your email.
      </p>

      <div style={{ display: "flex", gap: 10 }}>
        <button type="button" onClick={onClose}
          style={{ flex: 1, padding: "11px", borderRadius: 8,
            border: "2px solid #e2e8f0", background: "transparent",
            color: "#64748b", fontWeight: 700, fontSize: "0.875rem",
            cursor: "pointer" }}>
          Cancel
        </button>
        <button type="submit" disabled={loading}
          style={{ flex: 2, padding: "11px", borderRadius: 8, border: "none",
            background: loading ? "#7dd3fc" : "#0ea5e9",
            color: "#fff", fontWeight: 700, fontSize: "0.875rem",
            cursor: loading ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          {loading ? "Sending OTP…" : <><ArrowRight size={15} /> Send Verification Code</>}
        </button>
      </div>
    </form>
  );
}

// ── Step 2: OTP Verification ──────────────────────────────────────────────
function OtpStep({ requestId, email, fullName, documentName, onClose }) {
  const [otp, setOtp]             = useState("");
  const [error, setError]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [resending, setResending] = useState(false);
  const [resendMsg, setResendMsg] = useState("");
  const [resendCount, setResendCount] = useState(0);
  const [success, setSuccess]     = useState(false);
  const [countdown, setCountdown] = useState(300); // 5 min in seconds

  // Countdown timer
  useEffect(() => {
    if (countdown <= 0 || success) return;
    const t = setTimeout(() => setCountdown(c => c - 1), 1000);
    return () => clearTimeout(t);
  }, [countdown, success]);

  const minutes = Math.floor(countdown / 60);
  const seconds = countdown % 60;
  const expired = countdown <= 0;

  async function handleVerify(e) {
    e.preventDefault();
    if (!otp.trim() || otp.length !== 6) { setError("Enter the 6-digit code"); return; }
    setError("");
    setLoading(true);
    try {
      const res = await axios.post(`${API}/download/verify`, {
        request_id: requestId,
        otp: otp.trim(),
      });
      if (res.data.verified && res.data.serve_url) {
        setSuccess(true);
        // Trigger download via the secure proxy endpoint.
        // serve_url is /download/serve/{token} — the real storage URL is
        // never exposed to the browser.
        setTimeout(() => {
          const a = document.createElement("a");
          a.href = `${API}${res.data.serve_url}`;
          a.download = documentName || "document.pdf";
          a.rel = "noopener noreferrer";
          a.click();
        }, 600);
      } else {
        setError("Verification failed. Please try again.");
      }
    } catch (err) {
      setError(err.response?.data?.detail || "Invalid OTP. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  async function handleResend() {
    if (resendCount >= 3) return;
    setResendMsg("");
    setError("");
    setResending(true);
    try {
      await axios.post(`${API}/download/resend`, { request_id: requestId });
      setResendCount(c => c + 1);
      setCountdown(300);
      setOtp("");
      setResendMsg("A new code has been sent to your email.");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to resend code.");
    } finally {
      setResending(false);
    }
  }

  // ── Success state ────────────────────────────────────────────────────
  if (success) {
    return (
      <div style={{ textAlign: "center", padding: "20px 0" }}>
        <motion.div
          initial={{ scale: 0.5, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: "spring", stiffness: 260, damping: 20 }}>
          <div style={{ width: 72, height: 72, borderRadius: "50%",
            background: "linear-gradient(135deg, #d1fae5, #a7f3d0)",
            display: "flex", alignItems: "center", justifyContent: "center",
            margin: "0 auto 20px" }}>
            <CheckCircle size={36} color="#059669" />
          </div>
        </motion.div>
        <h3 style={{ fontWeight: 800, color: "#1e3a5f", fontSize: "1.2rem", marginBottom: 8 }}>
          Verification Successful!
        </h3>
        <p style={{ color: "#64748b", fontSize: "0.9rem", lineHeight: 1.6, marginBottom: 24 }}>
          Your download has started. If it doesn't begin automatically,
          check your browser's download settings.
        </p>
        <button onClick={onClose}
          style={{ padding: "11px 32px", borderRadius: 8, border: "none",
            background: "#0ea5e9", color: "#fff", fontWeight: 700,
            fontSize: "0.875rem", cursor: "pointer" }}>
          Done
        </button>
      </div>
    );
  }

  return (
    <form onSubmit={handleVerify}>
      {/* Email indicator */}
      <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0",
        borderRadius: 10, padding: "12px 14px", marginBottom: 20,
        display: "flex", gap: 10, alignItems: "center" }}>
        <Mail size={16} color="#059669" />
        <div>
          <div style={{ fontWeight: 700, color: "#065f46", fontSize: "0.82rem" }}>
            Code sent to {email}
          </div>
          <div style={{ fontSize: "0.75rem", color: "#6b7280", marginTop: 2 }}>
            Hi {fullName} — check your inbox (and spam folder)
          </div>
        </div>
      </div>

      {/* OTP input */}
      <div style={{ marginBottom: 16 }}>
        <label style={{ display: "block", fontSize: "0.82rem", fontWeight: 700,
          color: "#374151", marginBottom: 8 }}>
          Verification Code
        </label>
        <input
          type="text"
          inputMode="numeric"
          maxLength={6}
          value={otp}
          onChange={e => { setOtp(e.target.value.replace(/\D/g, "")); setError(""); }}
          placeholder="Enter 6-digit code"
          autoFocus
          style={{
            width: "100%", padding: "14px 16px", borderRadius: 8,
            border: `2px solid ${error ? "#ef4444" : "#e2e8f0"}`,
            fontSize: "1.6rem", fontFamily: "monospace", letterSpacing: "0.3em",
            textAlign: "center", background: "#f8fafc", color: "#1e3a5f",
            outline: "none", boxSizing: "border-box",
            transition: "border-color 0.15s",
          }}
          onFocus={e => e.target.style.borderColor = error ? "#ef4444" : "#0ea5e9"}
          onBlur={e => e.target.style.borderColor = error ? "#ef4444" : "#e2e8f0"}
        />
        {error && <p style={{ color: "#ef4444", fontSize: "0.78rem", margin: "5px 0 0" }}>{error}</p>}
      </div>

      {/* Timer + resend */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center",
        marginBottom: 20, fontSize: "0.78rem" }}>
        <span style={{ color: expired ? "#ef4444" : "#64748b" }}>
          {expired
            ? "⚠️ Code expired"
            : `Expires in ${minutes}:${String(seconds).padStart(2, "0")}`}
        </span>
        <button type="button" onClick={handleResend}
          disabled={resending || resendCount >= 3}
          style={{ background: "none", border: "none", cursor: resendCount >= 3 ? "not-allowed" : "pointer",
            color: resendCount >= 3 ? "#94a3b8" : "#0ea5e9",
            fontWeight: 700, fontSize: "0.78rem",
            display: "flex", alignItems: "center", gap: 4 }}>
          <RefreshCw size={12} />
          {resending ? "Sending…" : resendCount >= 3 ? "Max resends reached" : "Resend Code"}
        </button>
      </div>

      {resendMsg && (
        <div style={{ background: "#f0fdf4", border: "1px solid #bbf7d0",
          borderRadius: 8, padding: "9px 12px", marginBottom: 14,
          color: "#065f46", fontSize: "0.78rem" }}>
          ✓ {resendMsg}
        </div>
      )}

      <div style={{ display: "flex", gap: 10 }}>
        <button type="button" onClick={onClose}
          style={{ flex: 1, padding: "11px", borderRadius: 8,
            border: "2px solid #e2e8f0", background: "transparent",
            color: "#64748b", fontWeight: 700, fontSize: "0.875rem",
            cursor: "pointer" }}>
          Cancel
        </button>
        <button type="submit" disabled={loading || otp.length !== 6 || expired}
          style={{ flex: 2, padding: "11px", borderRadius: 8, border: "none",
            background: (loading || otp.length !== 6 || expired) ? "#7dd3fc" : "#0ea5e9",
            color: "#fff", fontWeight: 700, fontSize: "0.875rem",
            cursor: (loading || otp.length !== 6 || expired) ? "not-allowed" : "pointer",
            display: "flex", alignItems: "center", justifyContent: "center", gap: 8 }}>
          {loading ? "Verifying…" : <><Shield size={14} /> Verify & Download</>}
        </button>
      </div>
    </form>
  );
}

// ── Main DownloadModal ────────────────────────────────────────────────────
export default function DownloadModal({ open, onClose, document: doc, userId, guestId }) {
  const [step, setStep]           = useState("form"); // "form" | "otp" | "guest_blocked" | "limit_blocked"
  const [otpData, setOtpData]     = useState(null);

  // Reset step whenever modal opens — also route guests immediately to blocked screen
  useEffect(() => {
    if (open) {
      setOtpData(null);
      setStep(userId ? "form" : "guest_blocked");
    }
  }, [open, doc?.id, userId]);

  if (!open || !doc) return null;

  function handleFormSuccess({ requestId, email, fullName }) {
    setOtpData({ requestId, email, fullName });
    setStep("otp");
  }

  // Called from InfoForm when the backend returns a rate-limit or guest error
  function handleBlockedError(message) {
    // Distinguish the two block types by message content
    if (message && message.toLowerCase().includes("sign in")) {
      setStep("guest_blocked");
    } else if (message && message.toLowerCase().includes("download limit")) {
      setStep("limit_blocked");
    }
    // Other errors stay on the form (apiError renders inline)
  }

  function handleClose() {
    setStep("form");
    setOtpData(null);
    onClose();
  }

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="download-overlay"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={handleClose}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 4000, padding: 20,
          }}>
          <motion.div
            key="download-card"
            initial={{ scale: 0.88, opacity: 0, y: 24 }}
            animate={{ scale: 1,    opacity: 1, y: 0 }}
            exit={  { scale: 0.88, opacity: 0, y: 24 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            onClick={e => e.stopPropagation()}
            style={{
              background: "#fff", borderRadius: 20, padding: 32,
              maxWidth: 500, width: "100%",
              maxHeight: "90vh", overflowY: "auto",
              boxShadow: "0 24px 80px rgba(30,58,95,0.24)",
            }}>

            {/* Header */}
            <div style={{ display: "flex", justifyContent: "space-between",
              alignItems: "flex-start", marginBottom: 24 }}>
              <div>
                {/* Step indicator — only shown for the active download flow */}
                {(step === "form" || step === "otp") && (
                  <div style={{ display: "flex", gap: 6, marginBottom: 8 }}>
                    {["form", "otp"].map((s) => (
                      <div key={s} style={{
                        width: 28, height: 4, borderRadius: 2,
                        background: (s === step || (step === "otp" && s === "form"))
                          ? "#0ea5e9" : "#e2e8f0",
                        transition: "background 0.3s",
                      }} />
                    ))}
                  </div>
                )}
                <h2 style={{ fontWeight: 900, color: "#1e3a5f", fontSize: "1.25rem", margin: 0 }}>
                  {step === "form"          ? "Download Document"
                   : step === "otp"         ? "Verify Your Email"
                   : step === "guest_blocked" ? "Sign In Required"
                   :                           "Download Limit Reached"}
                </h2>
                <p style={{ color: "#64748b", fontSize: "0.82rem", marginTop: 4 }}>
                  {step === "form"
                    ? "Please provide your details to proceed"
                    : step === "otp"
                    ? "Enter the 6-digit code we sent you"
                    : "\u00a0"}
                </p>
              </div>
              <button onClick={handleClose}
                style={{ background: "#f1f5f9", border: "none", borderRadius: 8,
                  width: 32, height: 32, cursor: "pointer", color: "#374151",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  flexShrink: 0, marginLeft: 12 }}>
                <X size={16} />
              </button>
            </div>

            {/* Step content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: step === "otp" ? 30 : -30 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: step === "otp" ? -30 : 30 }}
                transition={{ duration: 0.22 }}>

                {/* ── Guest blocked ── */}
                {step === "guest_blocked" && (
                  <div style={{ textAlign: "center", padding: "12px 0 4px" }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: "50%",
                      background: "linear-gradient(135deg, #fef3c7, #fde68a)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      margin: "0 auto 18px",
                    }}>
                      <Shield size={28} color="#d97706" />
                    </div>
                    <h3 style={{ fontWeight: 800, color: "#1e3a5f", fontSize: "1.1rem", marginBottom: 8 }}>
                      Sign In Required
                    </h3>
                    <p style={{ color: "#64748b", fontSize: "0.875rem", lineHeight: 1.6,
                      marginBottom: 24, maxWidth: 320, margin: "0 auto 24px" }}>
                      Guest users cannot download documents.
                      Please sign in to access document downloads.
                    </p>
                    <button onClick={handleClose}
                      style={{ padding: "11px 32px", borderRadius: 8, border: "none",
                        background: "#0ea5e9", color: "#fff", fontWeight: 700,
                        fontSize: "0.875rem", cursor: "pointer" }}>
                      Close
                    </button>
                  </div>
                )}

                {/* ── Daily limit blocked ── */}
                {step === "limit_blocked" && (
                  <div style={{ textAlign: "center", padding: "12px 0 4px" }}>
                    <div style={{
                      width: 64, height: 64, borderRadius: "50%",
                      background: "linear-gradient(135deg, #fee2e2, #fecaca)",
                      display: "flex", alignItems: "center", justifyContent: "center",
                      margin: "0 auto 18px",
                    }}>
                      <Shield size={28} color="#dc2626" />
                    </div>
                    <h3 style={{ fontWeight: 800, color: "#1e3a5f", fontSize: "1.1rem", marginBottom: 8 }}>
                      Download Limit Reached
                    </h3>
                    <p style={{ color: "#64748b", fontSize: "0.875rem", lineHeight: 1.6,
                      marginBottom: 24, maxWidth: 340, margin: "0 auto 24px" }}>
                      You have reached today's download limit.
                      <br />Please try again after 24 hours.
                    </p>
                    <button onClick={handleClose}
                      style={{ padding: "11px 32px", borderRadius: 8, border: "none",
                        background: "#0ea5e9", color: "#fff", fontWeight: 700,
                        fontSize: "0.875rem", cursor: "pointer" }}>
                      Close
                    </button>
                  </div>
                )}

                {step === "form" && (
                  <InfoForm
                    doc={doc}
                    userId={userId}
                    guestId={guestId}
                    onSuccess={handleFormSuccess}
                    onBlockedError={handleBlockedError}
                    onClose={handleClose}
                  />
                )}
                {step === "otp" && (
                  <OtpStep
                    requestId={otpData.requestId}
                    email={otpData.email}
                    fullName={otpData.fullName}
                    documentName={doc.document_name}
                    onClose={handleClose}
                  />
                )}
              </motion.div>
            </AnimatePresence>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
