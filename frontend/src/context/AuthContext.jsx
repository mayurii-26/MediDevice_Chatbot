/**
 * AuthContext.jsx
 * Provides global auth state to the entire app.
 * - session: the Supabase session (null if guest)
 * - user: the authenticated user object (null if guest)
 * - isGuest: true when no active Supabase session
 * - authLoading: true while session is being checked on startup
 */
import { createContext, useContext, useEffect, useState } from "react";
import { supabase } from "../lib/supabase";
import { getGuestSessionId } from "../lib/guestSession";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [session, setSession]       = useState(null);
  const [authLoading, setLoading]   = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setLoading(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange((_, s) => {
      setSession(s);
      setLoading(false);
    });

    return () => listener.subscription.unsubscribe();
  }, []);

  const user    = session?.user || null;
  const isGuest = !session;
  // Guest session ID — stable for the lifetime of the browser tab
  const guestId = isGuest ? getGuestSessionId() : null;

  return (
    <AuthContext.Provider value={{ session, user, isGuest, guestId, authLoading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
