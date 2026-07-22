/**
 * AdminAuthContext.jsx
 *
 * Completely independent auth context for the admin portal.
 * Has NO dependency on Supabase, the user AuthContext, or any user session.
 *
 * Token lifecycle:
 *   - Stored in localStorage under key "admin_token"
 *   - On mount, checks for an existing valid-looking token
 *   - adminLogin()  — POST /admin/login, stores token, sets isAdminAuth=true
 *   - adminLogout() — clears token, sets isAdminAuth=false
 *
 * Usage:
 *   const { isAdminAuth, adminLoading, adminLogin, adminLogout } = useAdminAuth();
 */
import { createContext, useContext, useEffect, useState, useCallback } from "react";

const ADMIN_TOKEN_KEY = "admin_token";
const API_BASE        = "http://127.0.0.1:8000";

const AdminAuthContext = createContext(null);

export function AdminAuthProvider({ children }) {
  const [isAdminAuth,  setIsAdminAuth]  = useState(false);
  const [adminLoading, setAdminLoading] = useState(true);  // true until initial check done
  const [adminError,   setAdminError]   = useState("");

  // ── On mount: check if a stored token exists ──────────────────────────
  useEffect(() => {
    const token = localStorage.getItem(ADMIN_TOKEN_KEY);
    if (token) {
      // Lightweight check: token exists → treat as authenticated.
      // The backend will reject it with 401 if it's expired.
      setIsAdminAuth(true);
    }
    setAdminLoading(false);
  }, []);

  // ── Login ──────────────────────────────────────────────────────────────
  const adminLogin = useCallback(async (username, password) => {
    setAdminError("");
    try {
      const res = await fetch(`${API_BASE}/admin/login`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) {
        setAdminError(data.detail || "Login failed.");
        return false;
      }
      localStorage.setItem(ADMIN_TOKEN_KEY, data.token);
      setIsAdminAuth(true);
      return true;
    } catch (err) {
      setAdminError("Network error — could not reach server.");
      return false;
    }
  }, []);

  // ── Logout ─────────────────────────────────────────────────────────────
  const adminLogout = useCallback(() => {
    localStorage.removeItem(ADMIN_TOKEN_KEY);
    setIsAdminAuth(false);
  }, []);

  // ── Token accessor ─────────────────────────────────────────────────────
  const getAdminToken = useCallback(
    () => localStorage.getItem(ADMIN_TOKEN_KEY),
    []
  );

  return (
    <AdminAuthContext.Provider
      value={{
        isAdminAuth,
        adminLoading,
        adminError,
        adminLogin,
        adminLogout,
        getAdminToken,
      }}
    >
      {children}
    </AdminAuthContext.Provider>
  );
}

export function useAdminAuth() {
  const ctx = useContext(AdminAuthContext);
  if (!ctx) throw new Error("useAdminAuth must be used inside <AdminAuthProvider>");
  return ctx;
}
