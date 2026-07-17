/**
 * SessionTimeoutModal.jsx
 *
 * Displays a modal informing the user their session has expired due to inactivity.
 * Styled to match the design system used across the MediDevice AI project.
 */

import { motion, AnimatePresence } from "framer-motion";
import { AlertCircle, LogOut } from "lucide-react";

export default function SessionTimeoutModal({ show, onClose }) {
  return (
    <AnimatePresence>
      {show && (
        <>
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            style={{
              position: "fixed",
              top: 0,
              left: 0,
              right: 0,
              bottom: 0,
              background: "rgba(0, 0, 0, 0.5)",
              zIndex: 9998,
              backdropFilter: "blur(4px)",
            }}
            onClick={onClose}
          />

          {/* Modal */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: 20 }}
            transition={{ duration: 0.25, ease: "easeOut" }}
            style={{
              position: "fixed",
              top: "50%",
              left: "50%",
              transform: "translate(-50%, -50%)",
              zIndex: 9999,
              background: "#fff",
              borderRadius: 16,
              boxShadow: "0 20px 60px rgba(30, 58, 95, 0.2)",
              border: "1px solid #e2e8f0",
              padding: "32px",
              maxWidth: 460,
              width: "90%",
            }}
          >
            {/* Icon */}
            <div style={{ textAlign: "center", marginBottom: 20 }}>
              <div
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  justifyContent: "center",
                  width: 56,
                  height: 56,
                  borderRadius: "50%",
                  background: "#fef3c7",
                  marginBottom: 12,
                }}
              >
                <AlertCircle size={28} color="#f59e0b" />
              </div>
              <h2
                style={{
                  fontSize: "1.5rem",
                  fontWeight: 800,
                  color: "#1e3a5f",
                  margin: "0 0 8px",
                  letterSpacing: "-0.4px",
                }}
              >
                Session Expired
              </h2>
              <p
                style={{
                  color: "#64748b",
                  fontSize: "0.95rem",
                  margin: 0,
                  lineHeight: 1.5,
                }}
              >
                Your session has expired due to inactivity. Please sign in again to continue.
              </p>
            </div>

            {/* Button */}
            <button
              onClick={onClose}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: 8,
                width: "100%",
                padding: "13px 0",
                borderRadius: 10,
                border: "none",
                background: "#0ea5e9",
                color: "#fff",
                fontWeight: 700,
                fontSize: "1rem",
                cursor: "pointer",
                boxShadow: "0 4px 16px rgba(14, 165, 233, 0.3)",
                transition: "all 0.18s",
                fontFamily: "inherit",
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = "#0284c7";
                e.currentTarget.style.transform = "translateY(-1px)";
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = "#0ea5e9";
                e.currentTarget.style.transform = "none";
              }}
            >
              <LogOut size={18} />
              <span>Sign In Again</span>
            </button>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
