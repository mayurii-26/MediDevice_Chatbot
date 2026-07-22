/**
 * AdminContactRequests.jsx — Route: /admin/contact-requests
 *
 * GET  /admin/contact-requests?limit=20&offset=0
 * PATCH /admin/contact-requests/{id}/status
 *
 * Columns:
 *   Name | Email | Phone | Address | Message | Reason |
 *   Submission Type | Date | Time | Status
 *
 * All form types stored (Pricing & Purchasing, Sample Report Request, General Support).
 * Ordered: newest first.
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated, adminFetch } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";

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

function truncate(str, n = 50) {
  if (!str) return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

// ── Submission type badge ─────────────────────────────────────────────────────
const SUBMISSION_STYLES = {
  "Pricing & Purchasing":  { bg: "#f0f9ff", color: "#0369a1", border: "#bae6fd" },
  "Sample Report Request": { bg: "#fdf4ff", color: "#7e22ce", border: "#e9d5ff" },
  "General Support":       { bg: "#f0fdf4", color: "#15803d", border: "#bbf7d0" },
  "General Inquiry":       { bg: "#f8fafc", color: "#475569", border: "#e2e8f0" },
};

function SubTypeBadge({ value }) {
  const style = SUBMISSION_STYLES[value] || { bg: "#f8fafc", color: "#475569", border: "#e2e8f0" };
  return (
    <span style={{
      display:      "inline-block",
      padding:      "3px 10px",
      borderRadius: 20,
      fontSize:     "0.72rem",
      fontWeight:   700,
      background:   style.bg,
      color:        style.color,
      border:       `1px solid ${style.border}`,
      whiteSpace:   "nowrap",
    }}>
      {value || "General Support"}
    </span>
  );
}

// ── Status dropdown ───────────────────────────────────────────────────────────
const STATUS_STYLES = {
  "Pending":     { bg: "#fef9c3", color: "#854d0e" },
  "In Progress": { bg: "#dbeafe", color: "#1d4ed8" },
  "Resolved":    { bg: "#dcfce7", color: "#166534" },
};

function StatusDropdown({ rowId, current, onUpdated }) {
  const [loading, setLoading] = useState(false);

  async function handleChange(e) {
    const newStatus = e.target.value;
    setLoading(true);
    try {
      await adminFetch(`/admin/contact-requests/${rowId}/status`, {
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
        padding:    "4px 10px", borderRadius: 8,
        fontSize:   "0.75rem", fontWeight: 600,
        background: s.bg, color: s.color,
        border:     `1px solid ${s.color}44`,
        cursor:     loading ? "wait" : "pointer",
        outline:    "none", minWidth: 108,
      }}
    >
      <option value="Pending">Pending</option>
      <option value="In Progress">In Progress</option>
      <option value="Resolved">Resolved</option>
    </select>
  );
}

// ── Expandable message cell ───────────────────────────────────────────────────
function MessageCell({ text }) {
  const [expanded, setExpanded] = useState(false);
  if (!text) return <span style={{ color: "#94a3b8" }}>—</span>;
  const short = text.length > 55;
  return (
    <div style={{ maxWidth: 220 }}>
      <span style={{ fontSize: "0.83rem", color: "#374151" }}>
        {expanded || !short ? text : truncate(text, 55)}
      </span>
      {short && (
        <button
          onClick={() => setExpanded(x => !x)}
          style={{
            marginLeft:  6,
            fontSize:    "0.72rem",
            color:       "#6366f1",
            background:  "none",
            border:      "none",
            cursor:      "pointer",
            fontWeight:  600,
            padding:     0,
            verticalAlign: "middle",
          }}
        >
          {expanded ? "less" : "more"}
        </button>
      )}
    </div>
  );
}

// ── Pagination controls ───────────────────────────────────────────────────────
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
      gap:            10,
    }}>
      <span style={{ fontSize: "0.8rem", color: "#94a3b8" }}>
        Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
      </span>
      <div style={{ display: "flex", gap: 6 }}>
        {[
          { label: "← Prev", disabled: page === 1,         off: offset - limit },
          { label: "Next →", disabled: page >= totalPgs,   off: offset + limit },
        ].map(btn => (
          <button
            key={btn.label}
            disabled={btn.disabled}
            onClick={() => onPage(Math.max(0, btn.off))}
            style={{
              padding:    "6px 14px", borderRadius: 8, fontSize: "0.8rem",
              fontWeight: 600, border: "1.5px solid #e2e8f0",
              background: btn.disabled ? "#f8fafc" : "#fff",
              color:      btn.disabled ? "#cbd5e1" : "#475569",
              cursor:     btn.disabled ? "not-allowed" : "pointer",
            }}
          >
            {btn.label}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminContactRequests() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off = 0) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/contact-requests", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  function handleStatusUpdated(rowId, newStatus) {
    setData(prev => ({
      ...prev,
      rows: prev.rows.map(r => r.id === rowId ? { ...r, status: newStatus } : r),
    }));
  }

  // Column definitions
  const COLS = [
    {
      key:    "name",
      label:  "Name",
      render: v => <strong style={{ color: "#0f172a" }}>{v || "—"}</strong>,
    },
    { key: "email",    label: "Email",   render: v => <span style={{ fontSize: "0.83rem" }}>{v || "—"}</span> },
    { key: "phone",    label: "Phone",   render: v => v || "—" },
    {
      key:    "address",
      label:  "Address",
      render: v => <span style={{ fontSize: "0.82rem", color: "#475569" }}>{truncate(v, 40) || "—"}</span>,
    },
    {
      key:    "message",
      label:  "Message",
      render: v => <MessageCell text={v} />,
    },
    {
      key:    "reason",
      label:  "Reason",
      render: v => (
        <span style={{
          padding: "2px 10px", borderRadius: 20,
          background: "#f0f9ff", color: "#0284c7",
          fontSize: "0.72rem", fontWeight: 600, whiteSpace: "nowrap",
        }}>
          {v || "—"}
        </span>
      ),
    },
    {
      key:    "submission_type",
      label:  "Submission Type",
      render: v => <SubTypeBadge value={v} />,
    },
    { key: "created_at", label: "Date", render: fmtDate },
    { key: "created_at", label: "Time", render: fmtTime, secondKey: true },
    {
      key:    "status",
      label:  "Status",
      render: (v, row) => (
        <StatusDropdown rowId={row.id} current={v} onUpdated={handleStatusUpdated} />
      ),
    },
  ];

  return (
    <AdminPageShell
      title="Contact Requests"
      description="All contact form submissions — Pricing & Purchasing, Sample Report, General Support. Newest first."
    >
      {error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
          borderRadius: 10, padding: "12px 16px", marginBottom: 20,
          fontSize: "0.875rem", fontWeight: 600,
        }}>
          ⚠ {error}
        </div>
      )}

      <div style={{
        background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14,
        overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
      }}>
        <div style={{ overflowX: "auto" }}>
          <table style={{ width: "100%", borderCollapse: "collapse", minWidth: 1000 }}>
            <thead>
              <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
                {COLS.map((col, i) => (
                  <th key={`${col.label}-${i}`} style={{
                    padding:       "12px 14px",
                    textAlign:     "left",
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
                ? Array.from({ length: 5 }).map((_, i) => (
                  <tr key={i}>
                    {COLS.map((_, j) => (
                      <td key={j} style={{ padding: "13px 14px" }}>
                        <div style={{
                          height: 14, background: "#f1f5f9", borderRadius: 5,
                          width: j === 4 ? "80%" : "55%",
                          animation: "pulse 1.4s ease-in-out infinite",
                        }} />
                      </td>
                    ))}
                  </tr>
                ))
                : data.rows.length === 0
                  ? (
                    <tr>
                      <td colSpan={COLS.length} style={{
                        padding:   "56px 16px",
                        textAlign: "center",
                        color:     "#94a3b8",
                        fontSize:  "0.9rem",
                      }}>
                        No contact requests yet. Run the DB migration first if this is new.
                      </td>
                    </tr>
                  )
                  : data.rows.map((row, ri) => (
                    <tr
                      key={row.id || ri}
                      style={{
                        borderBottom: ri < data.rows.length - 1 ? "1px solid #f1f5f9" : "none",
                      }}
                      onMouseEnter={e => e.currentTarget.style.background = "#fafafa"}
                      onMouseLeave={e => e.currentTarget.style.background = ""}
                    >
                      {COLS.map((col, ci) => (
                        <td key={`${col.label}-${ci}`} style={{
                          padding:  "13px 14px",
                          fontSize: "0.83rem",
                          color:    "#334155",
                          verticalAlign: "top",
                        }}>
                          {col.render
                            ? col.render(row[col.key], row)
                            : (row[col.key] || "—")}
                        </td>
                      ))}
                    </tr>
                  ))
              }
            </tbody>
          </table>
        </div>

        {data.total > PAGE_SIZE && (
          <Pagination
            offset={offset}
            limit={PAGE_SIZE}
            total={data.total}
            onPage={load}
          />
        )}
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.4; }
        }
      `}</style>
    </AdminPageShell>
  );
}
