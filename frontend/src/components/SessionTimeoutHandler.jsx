/**
 * SessionTimeoutHandler.jsx
 *
 * Orchestrates automatic session timeout for logged-in users:
 *   1. Arms the inactivity timer (via useSessionTimeout) — guests are excluded.
 *   2. On timeout: signs out via Supabase, shows the SessionTimeoutModal.
 *   3. Broadcasts logout to all open tabs via BroadcastChannel so every tab
 *      logs out simultaneously (cross-tab sync).
 *   4. Listens for broadcast from other tabs and mirrors the logout locally.
 *
 * Mount this once at the root level (inside AuthProvider + BrowserRouter).
 * It renders nothing visible unless a timeout has occurred.
 */

import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";
import { useAuth } from "../context/AuthContext";
import { useSessionTimeout } from "../hooks/useSessionTimeout";
import SessionTimeoutModal from "./SessionTimeoutModal";

// BroadcastChannel name — shared across all tabs of the same origin
const CHANNEL_NAME = "mda_session";
const MSG_TIMEOUT  = "SESSION_TIMEOUT";

export default function SessionTimeoutHandler() {
  const { session, isGuest } = useAuth();
  const navigate             = useNavigate();
  const [showModal, setShowModal] = useState(false);
  const channelRef = useRef(null);

  // ── 1. Set up BroadcastChannel ──────────────────────────────────────────
  useEffect(() => {
    // BroadcastChannel is supported in all modern browsers
    if (!("BroadcastChannel" in window)) return;

    const channel = new BroadcastChannel(CHANNEL_NAME);
    channelRef.current = channel;

    channel.onmessage = (event) => {
      if (event.data === MSG_TIMEOUT) {
        // Another tab triggered timeout — mirror the logout locally
        // We don't call supabase.auth.signOut() again (it already ran in the
        // originating tab), but we do show the modal and redirect here.
        setShowModal(true);
      }
    };

    return () => {
      channel.close();
      channelRef.current = null;
    };
  }, []);

  // ── 2. Core timeout handler ─────────────────────────────────────────────
  const handleTimeout = useCallback(async () => {
    // Broadcast to all other open tabs first
    channelRef.current?.postMessage(MSG_TIMEOUT);

    // Sign out from Supabase (clears token + local storage)
    await supabase.auth.signOut();

    // Show the session-expired modal in this tab
    setShowModal(true);
  }, []);

  // ── 3. Arm the inactivity hook — only for authenticated non-guest users ──
  useSessionTimeout({
    isActive: !!session && !isGuest,
    onTimeout: handleTimeout,
  });

  // ── 4. Dismiss modal and navigate to login ──────────────────────────────
  const handleModalClose = useCallback(() => {
    setShowModal(false);
    navigate("/login", {
      replace: true,
      state: {
        message:
          "Your session has expired due to inactivity. Please sign in again.",
      },
    });
  }, [navigate]);

  return (
    <SessionTimeoutModal show={showModal} onClose={handleModalClose} />
  );
}
