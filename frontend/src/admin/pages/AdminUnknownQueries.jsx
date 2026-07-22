/**
 * AdminUnknownQueries.jsx — Route: /admin/unknown-queries
 *
 * Shows healthcare-domain queries that the chatbot could NOT answer.
 * Off-topic queries (weather, sports, movies) are excluded at write-time.
 *
 * Source: unanswered_queries table (deduplicated by normalised question)
 * GET  /admin/unknown-queries?limit=20&offset=0
 * PATCH /admin/unknown-queries/{id}/status
 *
 * Columns: Query | User | Date | Times Asked | Reason | Status
 * Ordered:  Newest first (last_asked_at DESC)
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated, adminFetch } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import { HelpCircle, RefreshCw, AlertTriangle } from "lucide-react";

const PAGE_SIZE = 20;

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtDate(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleDateString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch (_) { return val; }
}

function fmtTime(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleTimeString("en-IN", {
      hour: "2-digit", minute: "2-digit", hour12: true,
    });
  } catch (_) { return val; }
}

// ── Reason badge ─────────────────────────────────────────────────────────────
const REASON_STYLES = {
  "No Knowledge Match": { bg: "#fff7ed", color: "#c2410c", border: "#fed7aa" },
  "Low Confidence":     { bg: "#fefce8", color: "#a16207", border: "#fde68a" },
  "Unknown Device":     { bg: "#faf5ff", color: "#7c3aed", border: "#ddd6fe" },
};

function ReasonBadge({ value }) {
  const s = REASON_STYLES[value] || { bg: "#f1f5f9", color: "#475569", border: "#e2e8f0" };
  return (
    <span style={{
      display:    "inline-block",
      padding:    "3px 10px",
      borderRadius: 20,
      fontSize:   "0.72rem",
      fontWeight: 700,
      background: s.bg,
      color:      s.color,
      border:     `1px solid ${s.border}`,
      whiteSpace: "nowrap",
    }}>
      {value || "—"}
    </span>
  );
}

// ── Times asked badge ────────────────────────────────────────────────────────
function TimesAskedBadge({ value }) {
  const n = value || 1;
  const color = n >= 5 ? "#dc2626" : n >= 3 ? "#d97706" : "#0284c7";
  const bg    = n >= 5 ? "#fef2f2" : n >= 3 ? "#fffbeb" : "#f0f9ff";
  return (
    <span style={{
      display:        "inline-flex",
      alignItems:     "center",
      justifyContent: "center",
      minWidth:       32,
      padding:        "3px 10px",
      borderRadius:   20,
      fontSize:       "0.82rem",
      fontWeight:     800,
      background:     bg,
      color,
    }}>
      {n}
    </span>
  );
}

// ── Status dropdown ───────────────────────────────────────────────────────────
const STATUS_STYLES = {
  "Pending":  { bg: "#fef9c3", color: "#854d0e" },
  "Reviewed": { bg: "#dbeafe", color: "#1d4ed8" },
  "Resolved": { bg: "#dcfce7", color: "#166534" },
};

function StatusDropdown({ rowId, current, onUpdated }) {
  const [loading, setLoading] = useState(false);

  async function handleChange(e) {
    const newStatus = e.target.value;
    setLoading(true);
    try {
      await adminFetch(`/admin/unknown-queries/${rowId}/status`, {
        method: "PATCH",
        body:   JSON.stringify({ status: newStatus }),
      });
      onUpdated(rowId, newStatus);
    } catch (err) {
      alert(`Failed to update status: ${err.message}`);
    } finally {
      setLoading(false);
    }
  }

  const s = STATUS_STYLES[current] || { bg: "#f1f5f9", color: "#475569" };
  return (
    <select
      value={current}
      onChange={handleChange}
      disabled={loading}
      style={{
        padding:    "4px 10px",
        borderRadius: 8,
        fontSize:   "0.75rem",
        fontWeight: 600,
        background: s.bg,
        color:      s.color,
        border:     `1px solid ${s.color}44`,
        cursor:     loading ? "wait" : "pointer",
        outline:    "none",
        minWidth:   100,
      }}
    >
      <option value="Pending">Pending</option>
      <option value="Reviewed">Reviewed</option>
      <option value="Resolved">Resolved</option>
    </select>
  );
}

// ── Expandable query cell ─────────────────────────────────────────────────────
function QueryCell({ text }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return <span style={{ color: "#94a3b8" }}>—</span>;
  const isLong = text.length > 72;
  const display = !expanded && isLong ? text.slice(0, 72) + "…" : text;
  return (
    <div style={{ maxWidth: 380 }}>
      <span style={{ color: "#0f172a", fontWeight: 500, fontSize: "0.875rem" }}>
        {display}
      </span>
      {isLong && (
        <button
          onClick={() => setExpanded(x => !x)}
          style={{
            marginLeft: 6,
            fontSize:   "0.72rem",
            color:      "#6366f1",
            background: "none",
            border:     "none",
            cursor:     "pointer",
            fontWeight: 700,
            padding:    0,
          }}
        >
          {expanded ? "less" : "more"}
        </button>
      )}
    </div>
  );
}

// ── Skeleton row ─────────────────────────────────────────────────────────────
function SkeletonRow() {
  return (
    <tr>
      {[380, 80, 70, 60, 100, 100].map((w, i) => (
        <td key={i} style={{ padding: "13px 16px" }}>
          <div style={{
            height: 14, background: "#f1f5f9", borderRadius: 5,
            width: w, animation: "pulse 1.4s ease-in-out infinite",
          }} />
        </td>
      ))}
    </tr>
  );
}

// ── Pagination ────────────────────────────────────────────────────────────────
function Pagination({ offset, limit, total, onPage }) {
  const page     = Math.floor(offset / limit) + 1;
  const totalPgs = Math.ceil(total / limit) || 1;
  return (
    <div style={{
      display:        "flex",
      alignItems:     "center",
      justifyContent: "space-between",
      padding:        "14px 20px",
      borderTop:      "1px solid #f1f5f9",
      flexWrap:       "wrap",
      gap:            8,
    }}>
      <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
        Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div style={{ display: "flex", gap: 6 }}>
        {[
          { label: "← Prev", disabled: page === 1,        off: offset - limit },
          { label: "Next →", disabled: page >= totalPgs,  off: offset + limit },
        ].map(btn => (
          <button key={btn.label} disabled={btn.disabled}
            onClick={() => onPage(Math.max(0, btn.off))}
            style={{
              padding: "6px 14px", borderRadius: 8, fontSize: "0.8rem",
              fontWeight: 600, border: "1.5px solid #e2e8f0",
              background: btn.disabled ? "#f8fafc" : "#fff",
              color:      btn.disabled ? "#cbd5e1" : "#475569",
              cursor:     btn.disabled ? "not-allowed" : "pointer",
            }}>
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminUnknownQueries() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off = 0) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/unknown-queries", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  // Optimistic status update — no full reload
  function handleStatusUpdated(rowId, newStatus) {
    setData(prev => ({
      ...prev,
      rows: prev.rows.map(r => r.id === rowId ? { ...r, status: newStatus } : r),
    }));
  }

  // Summary counts
  const pending  = data.rows.filter(r => r.status === "Pending").length;
  const reviewed = data.rows.filter(r => r.status === "Reviewed").length;
  const resolved = data.rows.filter(r => r.status === "Resolved").length;

  return (
    <AdminPageShell
      title="Unknown Queries"
      description="Healthcare queries that could not be answered. Off-topic questions are excluded automatically."
    >
      {/* Header row */}
      <div style={{
        display:        "flex",
        alignItems:     "center",
        justifyContent: "space-between",
        marginBottom:   20,
        flexWrap:       "wrap",
        gap:            12,
      }}>
        {/* Mini summary pills */}
        <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {[
            { label: "Pending",  value: pending,  bg: "#fef9c3", color: "#854d0e" },
            { label: "Reviewed", value: reviewed, bg: "#dbeafe", color: "#1d4ed8" },
            { label: "Resolved", value: resolved, bg: "#dcfce7", color: "#166534" },
          ].map(p => (
            <span key={p.label} style={{
              padding:    "4px 12px", borderRadius: 20,
              fontSize:   "0.78rem", fontWeight: 700,
              background: p.bg, color: p.color,
            }}>
              {p.value} {p.label}
            </span>
          ))}
          <span style={{
            display:    "flex", alignItems: "center", gap: 5,
            fontSize:   "0.78rem", color: "#64748b", fontWeight: 600,
          }}>
            <AlertTriangle size={13} color="#f59e0b" />
            Only healthcare queries shown
          </span>
        </div>

        <button
          onClick={() => load(0)}
          disabled={loading}
          style={{
            display:    "flex", alignItems: "center", gap: 6,
            padding:    "7px 16px", borderRadius: 8,
            border:     "1.5px solid #e2e8f0",
            background: "#fff", color: "#475569",
            fontSize:   "0.82rem", fontWeight: 600,
            cursor:     loading ? "wait" : "pointer",
            opacity:    loading ? 0.6 : 1,
          }}
        >
          <RefreshCw size={14} style={{ animation: loading ? "spin 0.7s linear infinite" : "none" }} />
          Refresh
        </button>
      </div>

      {/* Error */}
      {error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
          borderRadius: 10, padding: "12px 16px", marginBottom: 18,
          fontSize: "0.875rem", fontWeight: 600,
        }}>
          ⚠ {error}
          {error.includes("exist") && (
            <span style={{ display: "block", marginTop: 4, fontWeight: 400, fontSize: "0.82rem" }}>
              Run <code>unanswered_queries_migration.sql</code> in Supabase SQL Editor first.
            </span>
          )}
        </div>
      )}

      {/* Table */}
      <div style={{
        background:   "#fff",
        border:       "1px solid #e2e8f0",
        borderRadius: 14,
        overflow:     "hidden",
        boxShadow:    "0 2px 8px rgba(0,0,0,0.05)",
      }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 860 }}>
            <thead>
              <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                {[
                  { label: "Query",       align: "left"   },
                  { label: "User",        align: "left"   },
                  { label: "Date",        align: "left"   },
                  { label: "Times Asked", align: "center" },
                  { label: "Reason",      align: "left"   },
                  { label: "Status",      align: "left"   },
                ].map(col => (
                  <th key={col.label} style={{
                    padding:       "12px 16px",
                    textAlign:     col.align,
                    fontSize:      "0.7rem",
                    fontWeight:    700,
                    color:         "#64748b",
                    textTransform: "uppercase",
                    letterSpacing: "0.06em",
                    whiteSpace:    "nowrap",
                  }}>
                    {col.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {loading
                ? Array.from({ length: 7 }).map((_, i) => <SkeletonRow key={i} />)
                : data.rows.length === 0
                  ? (
                    <tr>
                      <td colSpan={6} style={{
                        padding: "60px 16px", textAlign: "center",
                        color: "#94a3b8", fontSize: "0.9rem",
                      }}>
                        <div style={{ marginBottom: 10 }}>
                          <HelpCircle size={32} color="#cbd5e1" />
                        </div>
                        No unanswered healthcare queries yet.
                        <br />
                        <span style={{ fontSize: "0.8rem" }}>
                          They appear here when users ask about medical devices we don't have data for.
                        </span>
                      </td>
                    </tr>
                  )
                  : data.rows.map((row, ri) => (
                    <tr
                      key={row.id || ri}
                      style={{
                        borderBottom: ri < data.rows.length - 1 ? "1px solid #f1f5f9" : "none",
                        transition:   "background 0.15s",
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = "#fafafa"}
                      onMouseLeave={e => e.currentTarget.style.background = ""}
                    >
                      {/* Query */}
                      <td style={{ padding: "13px 16px", verticalAlign: "top" }}>
                        <QueryCell text={row.query} />
                      </td>

                      {/* User */}
                      <td style={{ padding: "13px 16px", color: "#64748b", fontSize: "0.82rem", whiteSpace: "nowrap" }}>
                        {row.user || "—"}
                      </td>

                      {/* Date */}
                      <td style={{ padding: "13px 16px", whiteSpace: "nowrap" }}>
                        <div style={{ fontSize: "0.82rem", color: "#334155" }}>{fmtDate(row.date)}</div>
                        <div style={{ fontSize: "0.72rem", color: "#94a3b8", marginTop: 2 }}>{fmtTime(row.date)}</div>
                      </td>

                      {/* Times Asked */}
                      <td style={{ padding: "13px 16px", textAlign: "center" }}>
                        <TimesAskedBadge value={row.times_asked} />
                      </td>

                      {/* Reason */}
                      <td style={{ padding: "13px 16px" }}>
                        <ReasonBadge value={row.reason} />
                      </td>

                      {/* Status dropdown */}
                      <td style={{ padding: "13px 16px" }}>
                        <StatusDropdown
                          rowId={row.id}
                          current={row.status}
                          onUpdated={handleStatusUpdated}
                        />
                      </td>
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {data.total > PAGE_SIZE && (
          <Pagination offset={offset} limit={PAGE_SIZE} total={data.total} onPage={load} />
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </AdminPageShell>
  );
}
