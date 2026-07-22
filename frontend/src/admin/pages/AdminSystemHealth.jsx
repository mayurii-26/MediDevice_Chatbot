/**
 * AdminSystemHealth.jsx — Route: /admin/system-health
 * GET /admin/system-health
 *
 * Live health table: Service, Status, Response Time, Detail
 * Services: Supabase DB, FAISS Index, BM25 Index, Storage, Gemini API, Response Time
 */
import { useEffect, useState, useCallback } from "react";
import { adminGet } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";

const STATUS_CFG = {
  ok:       { label: "Operational", dot: "#22c55e", bg: "#f0fdf4", text: "#16a34a" },
  degraded: { label: "Degraded",    dot: "#eab308", bg: "#fefce8", text: "#854d0e" },
  down:     { label: "Down",        dot: "#ef4444", bg: "#fef2f2", text: "#dc2626" },
  unknown:  { label: "Unknown",     dot: "#94a3b8", bg: "#f8fafc", text: "#475569" },
};

const SERVICE_ICONS = {
  "Supabase DB":    "🗄️",
  "FAISS Index":    "🔍",
  "BM25 Index":     "📑",
  "Storage":        "📦",
  "Gemini API":     "✨",
  "Response Time":  "⏱️",
};

function StatusBadge({ code }) {
  const c = STATUS_CFG[code] || STATUS_CFG.unknown;
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 7,
      padding: "4px 12px", borderRadius: 20,
      background: c.bg, border: `1px solid ${c.dot}44`,
    }}>
      <div style={{
        width: 8, height: 8, borderRadius: "50%",
        background: c.dot,
        boxShadow: `0 0 0 3px ${c.dot}30`,
      }} />
      <span style={{ fontSize: "0.78rem", fontWeight: 700, color: c.text }}>
        {c.label}
      </span>
    </div>
  );
}

export default function AdminSystemHealth() {
  const [data,      setData]      = useState(null);
  const [loading,   setLoading]   = useState(true);
  const [error,     setError]     = useState("");
  const [lastCheck, setLastCheck] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    adminGet("/admin/system-health")
      .then(d => { setData(d); setLastCheck(new Date()); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  const rows    = data?.rows    || [];
  const overall = data?.overall || "unknown";
  const oc      = STATUS_CFG[overall] || STATUS_CFG.unknown;

  return (
    <AdminPageShell
      title="System Health"
      description="Live status of all backend subsystems."
    >
      {/* Overall status banner + refresh */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 20,
      }}>
        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          background: oc.bg, border: `1px solid ${oc.dot}44`,
          borderRadius: 12, padding: "10px 18px",
        }}>
          <div style={{
            width: 10, height: 10, borderRadius: "50%", background: oc.dot,
            boxShadow: `0 0 0 4px ${oc.dot}30`,
          }} />
          <span style={{ fontWeight: 700, color: oc.text, fontSize: "0.9rem" }}>
            Overall: {oc.label}
          </span>
          {lastCheck && (
            <span style={{ color: "#94a3b8", fontSize: "0.75rem", marginLeft: 4 }}>
              — checked at {lastCheck.toLocaleTimeString("en-IN")}
            </span>
          )}
        </div>
        <button
          onClick={load}
          disabled={loading}
          style={{
            padding: "8px 18px", borderRadius: 8, fontSize: "0.82rem", fontWeight: 600,
            background: loading ? "#f1f5f9" : "#0ea5e9",
            color: loading ? "#94a3b8" : "#fff",
            border: "none", cursor: loading ? "not-allowed" : "pointer",
          }}
        >
          {loading ? "Checking…" : "🔄 Refresh"}
        </button>
      </div>

      {error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 10,
          padding: "12px 16px", color: "#dc2626", fontSize: "0.85rem", marginBottom: 16,
        }}>
          {error}
        </div>
      )}

      {/* Health table */}
      <div style={{
        background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
        overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {["Service", "Status", "Response Time", "Detail"].map(h => (
                <th key={h} style={{
                  padding: "11px 20px", textAlign: "left",
                  fontSize: "0.72rem", fontWeight: 700, color: "#64748b",
                  textTransform: "uppercase", letterSpacing: "0.05em",
                  borderBottom: "1px solid #e2e8f0",
                }}>
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 && !loading && (
              <tr>
                <td colSpan={4} style={{
                  padding: "48px 20px", textAlign: "center",
                  color: "#94a3b8", fontSize: "0.9rem",
                }}>
                  No health data yet.
                </td>
              </tr>
            )}
            {rows.map((row, i) => (
              <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}
                onMouseEnter={e => { e.currentTarget.style.background = "#f8fafc"; }}
                onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
              >
                {/* Service name */}
                <td style={{ padding: "14px 20px" }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <span style={{ fontSize: "1.1rem" }}>
                      {SERVICE_ICONS[row.service] || "🔧"}
                    </span>
                    <span style={{ fontWeight: 600, color: "#0f172a", fontSize: "0.88rem" }}>
                      {row.service}
                    </span>
                  </div>
                </td>
                {/* Status badge */}
                <td style={{ padding: "14px 20px" }}>
                  <StatusBadge code={row.status_code} />
                </td>
                {/* Response time */}
                <td style={{ padding: "14px 20px" }}>
                  <span style={{
                    fontFamily: "monospace", fontSize: "0.85rem",
                    color: row.response_time === "—" ? "#94a3b8" : "#0f172a",
                    fontWeight: 600,
                  }}>
                    {row.response_time || "—"}
                  </span>
                </td>
                {/* Detail */}
                <td style={{ padding: "14px 20px" }}>
                  <span style={{ fontSize: "0.82rem", color: "#475569" }}>
                    {row.detail || "—"}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AdminPageShell>
  );
}
