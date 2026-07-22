/**
 * AdminProtectedRoute.jsx
 *
 * Route guard for the admin portal.
 * - If adminLoading is true → renders nothing (avoids flash of login page).
 * - If isAdminAuth is false → redirects to /admin/login.
 * - Otherwise → renders children.
 *
 * Has NO dependency on Supabase or the user ProtectedRoute.
 */
import { Navigate, useLocation } from "react-router-dom";
import { useAdminAuth } from "../context/AdminAuthContext";

export default function AdminProtectedRoute({ children }) {
  const { isAdminAuth, adminLoading } = useAdminAuth();
  const location = useLocation();

  // Still checking localStorage on mount — don't flash the login page
  if (adminLoading) return null;

  if (!isAdminAuth) {
    return (
      <Navigate
        to="/admin/login"
        replace
        state={{ from: location }}
      />
    );
  }

  return children;
}
