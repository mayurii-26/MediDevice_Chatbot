/**
 * AdminLogin.jsx
 *
 * Standalone admin login page.
 * - Route: /admin/login
 * - POSTs to backend /admin/login endpoint (independent JWT, no Supabase).
 * - On success stores token via AdminAuthContext and redirects to /admin/dashboard.
 * - Already-authenticated admins are redirected immediately to /admin/dashboard.
 *
 * Completely separate from the user Login page.
 */
import { useState, useEffect } from "react";
import { useNavigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { ShieldCheck, User, Lock, ArrowRight, Stethoscope } from "lucide-react";
import { useAdminAuth } from "../context/AdminAuthContext";

export default function AdminLogin() {
  const { isAdminAuth, adminLoading, adminLogin, adminError } = useAdminAuth();
  const navigate  = useNavigate();
  const location  = useLocation();
  const from      = location.state?.from?.pathname || "/admin/dashboard";

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState("");

  // If already authenticated, skip the login page
  useEffect(() => {
    if (!adminLoading && isAdminAuth) {
      navigate("/admin/dashboard", { replace: true });
    }
  }, [isAdminAuth, adminLoading, navigate]);

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (!username.trim() || !password.trim()) {
      setError("Username and password are required.");
      return;
    }
    setLoading(true);
    const success = await adminLogin(username.trim(), password.trim());
    setLoading(false);
    if (success) {
      navigate(from, { replace: true });
    } else {
      setError(adminError || "Invalid credentials.");
    }
  }

  // Don't flash the form while checking localStorage
  if (adminLoading) return null;

  return (
    <div style={{
      minHeight:       "100vh",
      background:      "linear-gradient(135deg, #0f172a 0%, #1e293b 55%, #0f172a 100%)",
      display:         "flex",
      alignItems:      "center",
      justifyContent:  "center",
      padding:         "24px 16px",
      fontFamily:      "'Inter', 'Segoe UI', system-ui, sans-serif",
    }}>
      <motion.div
        initial={{ opacity: 0, y: 28 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: "easeOut" }}
        style={{
          background:    "#1e293b",
          borderRadius:  20,
          boxShadow:     "0 24px 80px rgba(0,0,0,0.5)",
          border:        "1px solid #334155",
          width:         "100%",
          maxWidth:      420,
          padding:       "44px 40px 40px",
        }}
      >
        {/* Brand mark */}
        <div style={{ textAlign: "center", marginBottom: 36 }}>
          <div style={{
            display:         "inline-flex",
            alignItems:      "center",
            gap:             10,
            marginBottom:    16,
          }}>
            <div style={{
              background:      "#0ea5e9",
              borderRadius:    10,
              padding:         9,
              display:         "flex",
            }}>
              <Stethoscope size={22} color="#fff" />
            </div>
            <span style={{ fontWeight: 900, fontSize: "1.25rem", color: "#f1f5f9" }}>
              MediDevice<span style={{ color: "#0ea5e9" }}>AI</span>
            </span>
          </div>

          {/* Admin badge */}
          <div style={{
            display:         "inline-flex",
            alignItems:      "center",
            gap:             6,
            background:      "rgba(14,165,233,0.12)",
            border:          "1px solid rgba(14,165,233,0.3)",
            borderRadius:    20,
            padding:         "4px 14px",
            marginBottom:    16,
          }}>
            <ShieldCheck size={13} color="#0ea5e9" />
            <span style={{ fontSize: "0.75rem", fontWeight: 600, color: "#0ea5e9", letterSpacing: "0.05em" }}>
              ADMIN PORTAL
            </span>
          </div>

          <h1 style={{ fontSize: "1.3rem", fontWeight: 700, color: "#f1f5f9", margin: 0 }}>
            Sign in to Admin
          </h1>
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: 6 }}>
            Access restricted to authorised administrators
          </p>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} noValidate>
          {/* Username */}
          <div style={{ marginBottom: 18 }}>
            <label style={{
              display:    "block",
              fontSize:   "0.8rem",
              fontWeight: 600,
              color:      "#94a3b8",
              marginBottom: 7,
              letterSpacing: "0.03em",
            }}>
              USERNAME
            </label>
            <div style={{ position: "relative" }}>
              <User
                size={16}
                color="#475569"
                style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }}
              />
              <input
                type="text"
                value={username}
                onChange={e => setUsername(e.target.value)}
                autoComplete="username"
                placeholder="admin"
                required
                style={{
                  width:          "100%",
                  padding:        "11px 14px 11px 40px",
                  background:     "#0f172a",
                  border:         "1px solid #334155",
                  borderRadius:   10,
                  color:          "#f1f5f9",
                  fontSize:       "0.9rem",
                  outline:        "none",
                  boxSizing:      "border-box",
                  transition:     "border-color 0.2s",
                }}
                onFocus={e  => { e.target.style.borderColor = "#0ea5e9"; }}
                onBlur={e   => { e.target.style.borderColor = "#334155"; }}
              />
            </div>
          </div>

          {/* Password */}
          <div style={{ marginBottom: 24 }}>
            <label style={{
              display:    "block",
              fontSize:   "0.8rem",
              fontWeight: 600,
              color:      "#94a3b8",
              marginBottom: 7,
              letterSpacing: "0.03em",
            }}>
              PASSWORD
            </label>
            <div style={{ position: "relative" }}>
              <Lock
                size={16}
                color="#475569"
                style={{ position: "absolute", left: 14, top: "50%", transform: "translateY(-50%)" }}
              />
              <input
                type="password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                autoComplete="current-password"
                placeholder="••••••••"
                required
                style={{
                  width:          "100%",
                  padding:        "11px 14px 11px 40px",
                  background:     "#0f172a",
                  border:         "1px solid #334155",
                  borderRadius:   10,
                  color:          "#f1f5f9",
                  fontSize:       "0.9rem",
                  outline:        "none",
                  boxSizing:      "border-box",
                  transition:     "border-color 0.2s",
                }}
                onFocus={e  => { e.target.style.borderColor = "#0ea5e9"; }}
                onBlur={e   => { e.target.style.borderColor = "#334155"; }}
              />
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div style={{
              background:   "rgba(239,68,68,0.1)",
              border:       "1px solid rgba(239,68,68,0.3)",
              borderRadius: 8,
              padding:      "10px 14px",
              marginBottom: 18,
              fontSize:     "0.85rem",
              color:        "#f87171",
            }}>
              {error}
            </div>
          )}

          {/* Submit */}
          <motion.button
            type="submit"
            disabled={loading}
            whileHover={{ scale: loading ? 1 : 1.01 }}
            whileTap={{  scale: loading ? 1 : 0.98 }}
            style={{
              width:          "100%",
              padding:        "12px 20px",
              background:     loading ? "#334155" : "#0ea5e9",
              border:         "none",
              borderRadius:   10,
              color:          "#fff",
              fontSize:       "0.9rem",
              fontWeight:     700,
              cursor:         loading ? "not-allowed" : "pointer",
              display:        "flex",
              alignItems:     "center",
              justifyContent: "center",
              gap:            8,
              transition:     "background 0.2s",
            }}
          >
            {loading ? "Signing in…" : (
              <>Sign in <ArrowRight size={16} /></>
            )}
          </motion.button>
        </form>

        {/* Footer note */}
        <p style={{
          textAlign:  "center",
          fontSize:   "0.75rem",
          color:      "#475569",
          marginTop:  24,
          marginBottom: 0,
        }}>
          This portal is for administrators only.<br />
          Unauthorised access is strictly prohibited.
        </p>
      </motion.div>
    </div>
  );
}
