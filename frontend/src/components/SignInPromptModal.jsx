/**
 * SignInPromptModal.jsx
 * Shown to guest users when they attempt an action requiring authentication
 * (e.g. downloading a document).
 * Props:
 *   open     — boolean
 *   onClose  — () => void
 *   message  — optional custom message string
 */
import { motion, AnimatePresence } from "framer-motion";
import { Link } from "react-router-dom";
import { Lock } from "lucide-react";

export default function SignInPromptModal({ open, onClose, message }) {
  if (!open) return null;

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          key="signin-overlay"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
          style={{
            position: "fixed", inset: 0, background: "rgba(0,0,0,0.55)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 3000, padding: 24,
          }}>
          <motion.div
            key="signin-card"
            initial={{ scale: 0.88, opacity: 0, y: 24 }}
            animate={{ scale: 1,    opacity: 1, y: 0 }}
            exit={  { scale: 0.88, opacity: 0, y: 24 }}
            transition={{ type: "spring", stiffness: 320, damping: 26 }}
            onClick={e => e.stopPropagation()}
            style={{
              background: "#fff", borderRadius: 20, padding: 48,
              maxWidth: 440, width: "100%", textAlign: "center",
              boxShadow: "0 24px 80px rgba(30,58,95,0.22)",
            }}>

            {/* Icon */}
            <div style={{
              width: 64, height: 64, borderRadius: "50%",
              background: "linear-gradient(135deg, #e0f2fe, #bfdbfe)",
              display: "flex", alignItems: "center", justifyContent: "center",
              margin: "0 auto 24px",
            }}>
              <Lock size={28} color="#0ea5e9" />
            </div>

            <h2 style={{ fontSize: "1.4rem", fontWeight: 900, color: "#1e3a5f", marginBottom: 12 }}>
              Sign in to Download
            </h2>

            <p style={{ fontSize: "1rem", color: "#64748b", lineHeight: 1.7, marginBottom: 32 }}>
              {message || "Please login or create an account to download documents, save conversations, and unlock personalised AI assistance."}
            </p>

            <div style={{ display: "flex", gap: 14, justifyContent: "center", flexWrap: "wrap" }}>
              <Link to="/login" onClick={onClose} style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                padding: "13px 32px", borderRadius: 10,
                background: "#0ea5e9", color: "#fff",
                fontWeight: 700, fontSize: "1rem", textDecoration: "none",
                transition: "background 0.15s",
                boxShadow: "0 4px 16px rgba(14,165,233,0.3)",
              }}>
                Login
              </Link>
              <Link to="/register" onClick={onClose} style={{
                display: "inline-flex", alignItems: "center", justifyContent: "center",
                padding: "13px 32px", borderRadius: 10,
                border: "2px solid #1e3a5f", color: "#1e3a5f",
                fontWeight: 700, fontSize: "1rem", textDecoration: "none",
                transition: "all 0.15s",
              }}>
                Register
              </Link>
            </div>

            <button onClick={onClose} style={{
              marginTop: 20, background: "none", border: "none",
              color: "#94a3b8", cursor: "pointer", fontSize: "0.9rem",
            }}>
              Continue as guest
            </button>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
