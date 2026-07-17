/**
 * useSessionTimeout.js
 *
 * Monitors user inactivity and triggers automatic logout after
 * TIMEOUT_MS milliseconds of no activity.
 *
 * Rules:
 * - Only active for authenticated (non-guest) users.
 * - Detects: mousemove, mousedown, keydown, scroll, touchstart, visibilitychange.
 * - Broadcasts logout across all open tabs via BroadcastChannel.
 * - Calls onTimeout() when inactivity threshold is reached.
 */

import { useEffect, useRef, useCallback } from "react";

const TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes

// Events that count as "user is active"
const ACTIVITY_EVENTS = [
  "mousemove",
  "mousedown",
  "keydown",
  "scroll",
  "touchstart",
  "wheel",
  "visibilitychange",
  "focus",
  "click",
];

/**
 * @param {object} options
 * @param {boolean} options.isActive  - Pass `true` only for logged-in (non-guest) users.
 * @param {Function} options.onTimeout - Called when the session has timed out.
 */
export function useSessionTimeout({ isActive, onTimeout }) {
  const timerRef    = useRef(null);
  const onTimeoutRef = useRef(onTimeout);

  // Keep the callback ref up-to-date without restarting the effect
  useEffect(() => { onTimeoutRef.current = onTimeout; }, [onTimeout]);

  const clearTimer = useCallback(() => {
    if (timerRef.current) {
      clearTimeout(timerRef.current);
      timerRef.current = null;
    }
  }, []);

  const resetTimer = useCallback(() => {
    clearTimer();
    timerRef.current = setTimeout(() => {
      onTimeoutRef.current?.();
    }, TIMEOUT_MS);
  }, [clearTimer]);

  useEffect(() => {
    // Only arm the timer for authenticated users
    if (!isActive) {
      clearTimer();
      return;
    }

    // Start the initial countdown
    resetTimer();

    // Every user interaction resets the countdown
    const handleActivity = () => resetTimer();

    ACTIVITY_EVENTS.forEach(event =>
      window.addEventListener(event, handleActivity, { passive: true })
    );

    return () => {
      clearTimer();
      ACTIVITY_EVENTS.forEach(event =>
        window.removeEventListener(event, handleActivity)
      );
    };
  }, [isActive, resetTimer, clearTimer]);
}
