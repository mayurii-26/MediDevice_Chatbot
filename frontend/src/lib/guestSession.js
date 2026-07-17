/**
 * guestSession.js
 * Generates and reuses a guest session ID stored in sessionStorage.
 * Automatically expires when the browser tab is closed.
 */

const KEY = "mda_guest_session_id";

function generateUUID() {
  return "guest_" + (
    "10000000-1000-4000-8000-100000000000".replace(/[018]/g, c => {
      const r = crypto.getRandomValues(new Uint8Array(1))[0];
      return (Number(c) ^ (r & (15 >> (Number(c) / 4)))).toString(16);
    })
  );
}

export function getGuestSessionId() {
  let id = sessionStorage.getItem(KEY);
  if (!id) {
    id = generateUUID();
    sessionStorage.setItem(KEY, id);
  }
  return id;
}

export function clearGuestSession() {
  sessionStorage.removeItem(KEY);
}
