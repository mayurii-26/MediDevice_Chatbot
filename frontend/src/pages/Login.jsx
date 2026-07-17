import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { motion } from "framer-motion";
import { Activity, Mail, Lock, ArrowRight } from "lucide-react";
import { supabase } from "../lib/supabase";

function Login() {
  const [email, setEmail]     = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus]   = useState("");
  const [loading, setLoading] = useState(false);
  const navigate              = useNavigate();
  const location              = useLocation();
  const infoMessage           = location.state?.message || null;

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) navigate("/");
    });
  }, [navigate]);

  async function handleLogin(e) {
    e.preventDefault();
    setStatus("");
    setLoading(true);
    const { error } = await supabase.auth.signInWithPassword({
      email: email.trim(),
      password: password.trim(),
    });
    setLoading(false);
    if (error) { setStatus(error.message); return; }
    navigate("/");
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 55%, #f8fafc 100%)",
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "24px 16px",
    }}>
      <motion.div
        initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, ease: "easeOut" }}
        style={{
          background: "#fff", borderRadius: 20,
          boxShadow: "0 16px 60px rgba(30,58,95,0.14)",
          border: "1px solid #e0f2fe",
          width: "100%", maxWidth: 440,
          padding: "44px 40px 40px",
        }}
      >
        {/* Brand mark */}
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <Link to="/" style={{ textDecoration: "none", display: "inline-flex", alignItems: "center", gap: 10, marginBottom: 24 }}>
            <div style={{ background: "#0ea5e9", borderRadius: 10, padding: 8, display: "flex" }}>
              <Activity size={20} color="#fff" />
            </div>
            <span style={{ fontWeight: 900, fontSize: "1.2rem", color: "#1e3a5f" }}>
              MediDevice<span style={{ color: "#0ea5e9" }}>AI</span>
            </span>
          </Link>
          <h1 style={{ fontSize: "1.6rem", fontWeight: 800, color: "#1e3a5f", margin: "0 0 8px", letterSpacing: "-0.4px" }}>
            Welcome back
          </h1>
          <p style={{ color: "#64748b", fontSize: "0.95rem", margin: 0 }}>
            Sign in to access your saved conversations.
          </p>
        </div>

        <form onSubmit={handleLogin} style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          {/* Email */}
          <div>
            <label style={{ display: "block", fontWeight: 600, color: "#374151",
              fontSize: "0.875rem", marginBottom: 6 }}>
              Email
            </label>
            <div style={{ position: "relative" }}>
              <Mail size={16} color="#94a3b8" style={{
                position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)",
                pointerEvents: "none",
              }} />
              <input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
                style={{
                  width: "100%", padding: "11px 12px 11px 38px",
                  border: "1.5px solid #e2e8f0", borderRadius: 9,
                  fontSize: "0.95rem", color: "#1e3a5f", background: "#f8fafc",
                  outline: "none", boxSizing: "border-box",
                  transition: "border-color 0.18s",
                  fontFamily: "inherit",
                }}
                onFocus={e => e.target.style.borderColor = "#0ea5e9"}
                onBlur={e => e.target.style.borderColor = "#e2e8f0"}
              />
            </div>
          </div>

          {/* Password */}
          <div>
            <label style={{ display: "block", fontWeight: 600, color: "#374151",
              fontSize: "0.875rem", marginBottom: 6 }}>
              Password
            </label>
            <div style={{ position: "relative" }}>
              <Lock size={16} color="#94a3b8" style={{
                position: "absolute", left: 13, top: "50%", transform: "translateY(-50%)",
                pointerEvents: "none",
              }} />
              <input
                type="password"
                placeholder="Enter your password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
                style={{
                  width: "100%", padding: "11px 12px 11px 38px",
                  border: "1.5px solid #e2e8f0", borderRadius: 9,
                  fontSize: "0.95rem", color: "#1e3a5f", background: "#f8fafc",
                  outline: "none", boxSizing: "border-box",
                  transition: "border-color 0.18s",
                  fontFamily: "inherit",
                }}
                onFocus={e => e.target.style.borderColor = "#0ea5e9"}
                onBlur={e => e.target.style.borderColor = "#e2e8f0"}
              />
            </div>
          </div>

          {/* Messages */}
          {infoMessage && (
            <div style={{ padding: "10px 14px", borderRadius: 8, background: "#f0fdf4",
              border: "1px solid #bbf7d0", color: "#15803d", fontSize: "0.875rem" }}>
              {infoMessage}
            </div>
          )}
          {status && (
            <div style={{ padding: "10px 14px", borderRadius: 8, background: "#fff5f5",
              border: "1px solid #fecaca", color: "#dc2626", fontSize: "0.875rem" }}>
              {status}
            </div>
          )}

          {/* Submit */}
          <button type="submit" disabled={loading}
            style={{
              display: "flex", alignItems: "center", justifyContent: "center", gap: 8,
              padding: "13px 0", borderRadius: 9, border: "none",
              background: loading ? "#93c5fd" : "#0ea5e9",
              color: "#fff", fontWeight: 700, fontSize: "1rem",
              cursor: loading ? "not-allowed" : "pointer",
              boxShadow: loading ? "none" : "0 4px 16px rgba(14,165,233,0.3)",
              transition: "all 0.18s",
              fontFamily: "inherit",
            }}
            onMouseEnter={e => { if (!loading) e.currentTarget.style.background = "#0284c7"; }}
            onMouseLeave={e => { if (!loading) e.currentTarget.style.background = "#0ea5e9"; }}
          >
            {loading ? "Signing in…" : <><span>Sign In</span> <ArrowRight size={16} /></>}
          </button>
        </form>

        <p style={{ textAlign: "center", marginTop: 24, fontSize: "0.9rem", color: "#64748b" }}>
          Don't have an account?{" "}
          <Link to="/register" style={{ color: "#0ea5e9", fontWeight: 700, textDecoration: "none" }}>
            Create one
          </Link>
        </p>
      </motion.div>
    </div>
  );
}

export default Login;
