/**
 * adminApi.js
 *
 * Shared fetch utility for the admin portal.
 * Automatically injects the admin JWT from localStorage into every request.
 * Throws an Error with a human-readable message on non-2xx responses.
 *
 * Usage:
 *   import { adminGet, adminPost } from "../lib/adminApi";
 *   const data = await adminGet("/admin/dashboard/stats");
 */

const API_BASE        = "http://127.0.0.1:8000";
const ADMIN_TOKEN_KEY = "admin_token";

function getToken() {
  return localStorage.getItem(ADMIN_TOKEN_KEY) || "";
}

/** Core fetch — exported for one-off calls (PATCH, DELETE, etc.) */
export function adminFetch(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };
  return fetch(`${API_BASE}${path}`, { ...options, headers }).then(async res => {
    if (res.status === 401) {
      localStorage.removeItem(ADMIN_TOKEN_KEY);
      throw new Error("Session expired. Please log in again.");
    }
    if (!res.ok) {
      let detail = `HTTP ${res.status}`;
      try { const err = await res.json(); detail = err.detail || detail; } catch (_) {}
      throw new Error(detail);
    }
    return res.json();
  });
}

/** GET helper */
export function adminGet(path) {
  return adminFetch(path, { method: "GET" });
}

/** GET with query string params */
export function adminGetPaginated(path, { limit = 20, offset = 0 } = {}) {
  return adminFetch(`${path}?limit=${limit}&offset=${offset}`, { method: "GET" });
}

/** POST helper */
export function adminPost(path, body) {
  return adminFetch(path, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
