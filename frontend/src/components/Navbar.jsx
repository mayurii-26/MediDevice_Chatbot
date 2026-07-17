import { useState, useEffect } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import { Menu, X, Activity, User, LogOut } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { supabase } from "../lib/supabase";

const NAV_LINKS = [
  { label: "Home",      to: "/" },
  { label: "Products",  to: "/products" },
  { label: "Services",  to: "/services" },
  { label: "Resources", to: "/resources" },
  { label: "About",     to: "/about" },
  { label: "Contact",   to: "/contact" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen]         = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const location                = useLocation();
  const navigate                = useNavigate();
  const { user, isGuest }       = useAuth();

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => { setOpen(false); setProfileOpen(false); }, [location]);

  // Close profile dropdown on outside click
  useEffect(() => {
    if (!profileOpen) return;
    const handler = () => setProfileOpen(false);
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [profileOpen]);

  const handleLogout = async () => {
    await supabase.auth.signOut();
    navigate("/");
  };

  // Get initials from email
  const initials = user?.email
    ? user.email.slice(0, 2).toUpperCase()
    : "?";

  const displayName = user?.email
    ? user.email.split("@")[0]
    : "";

  return (
    <nav style={{
      position: "fixed", top: 0, left: 0, right: 0, zIndex: 900,
      background: scrolled ? "rgba(255,255,255,0.97)" : "rgba(255,255,255,0.88)",
      backdropFilter: "blur(14px)",
      borderBottom: scrolled ? "1px solid #e2e8f0" : "1px solid transparent",
      boxShadow: scrolled ? "0 2px 20px rgba(30,58,95,0.09)" : "none",
      transition: "all 0.25s",
    }}>
      <div style={{
        maxWidth: 1280, margin: "0 auto", padding: "0 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: 76,
      }}>
        {/* Logo */}
        <Link to="/" style={{ textDecoration: "none", display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{ background: "#0ea5e9", borderRadius: 10, padding: 8, display: "flex" }}>
            <Activity size={22} color="#fff" />
          </div>
          <span style={{ fontWeight: 900, fontSize: "1.3rem", color: "#1e3a5f", letterSpacing: "-0.4px" }}>
            MediDevice<span style={{ color: "#0ea5e9" }}>AI</span>
          </span>
        </Link>

        {/* Desktop links */}
        <ul style={{ display: "flex", gap: 2, listStyle: "none", margin: 0, padding: 0 }}
            className="ws-nav-desktop">
          {NAV_LINKS.map(({ label, to }) => {
            const active = location.pathname === to;
            return (
              <li key={to}>
                <Link to={to} style={{
                  textDecoration: "none", padding: "9px 16px", borderRadius: 9,
                  fontSize: "0.975rem", fontWeight: active ? 700 : 500,
                  color: active ? "#0ea5e9" : "#1e3a5f",
                  background: active ? "#e0f2fe" : "transparent",
                  transition: "all 0.15s", display: "block",
                }}
                onMouseEnter={e => { if (!active) { e.target.style.color = "#0ea5e9"; e.target.style.background = "#f0f9ff"; }}}
                onMouseLeave={e => { if (!active) { e.target.style.color = "#1e3a5f"; e.target.style.background = "transparent"; }}}>
                  {label}
                </Link>
              </li>
            );
          })}
        </ul>

        {/* CTA — guest vs logged-in */}
        <div style={{ display: "flex", gap: 10, alignItems: "center", position: "relative" }}
             className="ws-nav-cta">
          {isGuest ? (
            <>
              <Link to="/login" style={{
                textDecoration: "none", padding: "10px 20px", borderRadius: 9,
                fontSize: "0.975rem", fontWeight: 700, color: "#1e3a5f",
                border: "2px solid #1e3a5f", transition: "all 0.15s",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "#1e3a5f"; e.currentTarget.style.color = "#fff"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "#1e3a5f"; }}>
                Sign In
              </Link>
              <Link to="/register" style={{
                textDecoration: "none", padding: "10px 22px", borderRadius: 9,
                fontSize: "0.975rem", fontWeight: 700, color: "#fff",
                background: "#0ea5e9", transition: "all 0.15s",
                boxShadow: "0 2px 8px rgba(14,165,233,0.3)",
              }}
              onMouseEnter={e => { e.currentTarget.style.background = "#0284c7"; e.currentTarget.style.transform = "translateY(-1px)"; }}
              onMouseLeave={e => { e.currentTarget.style.background = "#0ea5e9"; e.currentTarget.style.transform = "none"; }}>
                Get Started
              </Link>
            </>
          ) : (
            <div style={{ position: "relative" }}>
              <button
                onMouseDown={e => { e.stopPropagation(); setProfileOpen(o => !o); }}
                style={{
                  display: "flex", alignItems: "center", gap: 9,
                  background: "#f0f9ff", border: "2px solid #bae6fd",
                  borderRadius: 40, padding: "7px 14px 7px 8px",
                  cursor: "pointer", transition: "all 0.15s",
                }}
                onMouseEnter={e => { e.currentTarget.style.borderColor = "#0ea5e9"; e.currentTarget.style.background = "#e0f2fe"; }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = "#bae6fd"; e.currentTarget.style.background = "#f0f9ff"; }}
              >
                {/* Avatar circle */}
                <div style={{
                  width: 30, height: 30, borderRadius: "50%",
                  background: "linear-gradient(135deg, #1e3a5f, #0ea5e9)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff", fontWeight: 800, fontSize: "0.75rem", flexShrink: 0,
                }}>
                  {initials}
                </div>
                <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#1e3a5f", maxWidth: 100,
                  overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {displayName}
                </span>
              </button>

              {/* Dropdown */}
              <AnimatePresence>
                {profileOpen && (
                  <motion.div
                    initial={{ opacity: 0, y: -6, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -6, scale: 0.97 }}
                    transition={{ duration: 0.14 }}
                    onMouseDown={e => e.stopPropagation()}
                    style={{
                      position: "absolute", top: "calc(100% + 10px)", right: 0,
                      background: "#fff", border: "1px solid #e2e8f0",
                      borderRadius: 12, boxShadow: "0 8px 32px rgba(30,58,95,0.14)",
                      minWidth: 200, zIndex: 999, overflow: "hidden",
                    }}
                  >
                    <div style={{ padding: "14px 16px", borderBottom: "1px solid #f1f5f9" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                          width: 36, height: 36, borderRadius: "50%",
                          background: "linear-gradient(135deg, #1e3a5f, #0ea5e9)",
                          display: "flex", alignItems: "center", justifyContent: "center",
                          color: "#fff", fontWeight: 800, fontSize: "0.85rem", flexShrink: 0,
                        }}>
                          {initials}
                        </div>
                        <div>
                          <div style={{ fontWeight: 700, color: "#1e3a5f", fontSize: "0.9rem" }}>
                            {displayName}
                          </div>
                          <div style={{ fontSize: "0.75rem", color: "#94a3b8",
                            overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                            maxWidth: 140 }}>
                            {user?.email}
                          </div>
                        </div>
                      </div>
                    </div>
                    <Link to="/chat" style={{
                      display: "flex", alignItems: "center", gap: 9,
                      padding: "11px 16px", textDecoration: "none",
                      color: "#374151", fontSize: "0.9rem", fontWeight: 500,
                      transition: "background 0.12s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "#f8fafc"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      <User size={15} color="#64748b" /> My Chats
                    </Link>
                    <button onClick={handleLogout} style={{
                      display: "flex", alignItems: "center", gap: 9,
                      width: "100%", padding: "11px 16px",
                      background: "none", border: "none", borderTop: "1px solid #f1f5f9",
                      color: "#ef4444", fontSize: "0.9rem", fontWeight: 600,
                      cursor: "pointer", textAlign: "left", transition: "background 0.12s",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "#fff5f5"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      <LogOut size={15} /> Sign Out
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </div>

        {/* Hamburger */}
        <button onClick={() => setOpen(o => !o)}
          style={{ display: "none", background: "none", border: "none",
                   cursor: "pointer", color: "#1e3a5f", padding: 6 }}
          className="ws-hamburger" aria-label="Menu">
          {open ? <X size={26} /> : <Menu size={26} />}
        </button>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -8 }} animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.18 }}
            style={{ background: "#fff", borderTop: "1px solid #e2e8f0", padding: "16px 24px 24px" }}>
            {NAV_LINKS.map(({ label, to }) => (
              <Link key={to} to={to} style={{
                display: "block", padding: "14px 0", fontWeight: 600,
                color: "#1e3a5f", textDecoration: "none",
                borderBottom: "1px solid #f1f5f9", fontSize: "1rem",
              }}>{label}</Link>
            ))}
            <div style={{ marginTop: 20 }}>
              {isGuest ? (
                <div style={{ display: "flex", gap: 10 }}>
                  <Link to="/login" style={{ flex: 1, textAlign: "center", padding: "12px",
                    borderRadius: 9, border: "2px solid #1e3a5f", fontWeight: 700,
                    color: "#1e3a5f", textDecoration: "none", fontSize: "0.95rem" }}>Sign In</Link>
                  <Link to="/register" style={{ flex: 1, textAlign: "center", padding: "12px",
                    borderRadius: 9, background: "#0ea5e9", fontWeight: 700,
                    color: "#fff", textDecoration: "none", fontSize: "0.95rem" }}>Get Started</Link>
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  <div style={{ padding: "10px 0", fontWeight: 600, color: "#1e3a5f",
                    fontSize: "0.95rem", borderBottom: "1px solid #f1f5f9", marginBottom: 8 }}>
                    Signed in as <span style={{ color: "#0ea5e9" }}>{displayName}</span>
                  </div>
                  <Link to="/chat" style={{ display: "flex", alignItems: "center", gap: 8,
                    padding: "12px 0", fontWeight: 600, color: "#374151",
                    textDecoration: "none", fontSize: "0.95rem" }}>
                    <User size={16} /> My Chats
                  </Link>
                  <button onClick={handleLogout} style={{
                    display: "flex", alignItems: "center", gap: 8,
                    padding: "12px 0", fontWeight: 700, color: "#ef4444",
                    background: "none", border: "none", cursor: "pointer",
                    fontSize: "0.95rem", textAlign: "left",
                  }}>
                    <LogOut size={16} /> Sign Out
                  </button>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      <style>{`
        @media (max-width: 900px) {
          .ws-nav-desktop, .ws-nav-cta { display: none !important; }
          .ws-hamburger { display: block !important; }
        }
      `}</style>
    </nav>
  );
}
