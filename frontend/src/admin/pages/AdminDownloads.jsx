/**
 * AdminDownloads.jsx — Route: /admin/downloads
 *
 * Full live download tracking table.
 * Source: GET /admin/downloads?limit=20&offset=0
 *
 * Columns:
 *   Full Name | Email | Document | Product | Download Time | OTP Verified | Status
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import { Download, ShieldCheck, ShieldX, RefreshCw } from "lucide-react";

const PAGE_SIZE = 20;

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtDateTime(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit", hour12: true,
    });
  } catch (_) { return val; }
}

function truncate(str, n = 36) {
  if (!str || str === "—") return "—";
  return str.length > n ? str.slice(0, n) + "…" : str;
}

// ── Status badge ──────────────────────────────────────────────────────────────
const STATUS_STYLE = {
  "Completed":  { bg: "#dcfce7", color: "#166534", dot: "#22c55e" },
  "OTP Verified": { bg: "#dbeafe", color: "#1d4ed8", dot: "#3b82f6" },
  "Pending OTP":  { bg: "#fef9c3", color: "#854d0e", dot: "#f59e0b" },
};

function StatusBadge({ value }) {
  const s = STATUS_STYLE[value] || { bg: "#f1f5f9", color: "#475569", dot: "#94a3b8" };
  return (
    <span style={{
      display:      "inline-flex",
      alignItems:   "center",
      gap:          5,
      padding:      "4px 10px",
      borderRadius: 20,
      fontSize:     "0.73rem",
      fontWeight:   700,
      background:   s.bg,
      color:        s.color,
      whiteSpace:   "nowrap",
    }}>
      <span style={{
        width: 7, height: 7, borderRadius: "50%", background: s.dot,
      }} />
      {value}
    </span>
  );
}

// ── OTP verified indicator ────────────────────────────────────────────────────
function OtpCell({ value }) {
  return value
    ? <ShieldCheck size={18} color="#22c55e" strokeWidth={2.5} />
    : <ShieldX    size={18} color="#f87171" strokeWidth={2.5} />;
}

// ── Skeleton row ─────────────────────────────────────────────────────────────
function SkeletonRow({ cols }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} style={{ padding: "14px 16px" }}>
          <div style={{
            height:    14,
            background:"#f1f5f9",
            borderRadius: 5,
            width:     i === 0 ? "70%" : i === 1 ? "80%" : "55%",
            animation: "pulse 1.4s ease-in-out infinite",
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

// ── Column definitions ────────────────────────────────────────────────────────
const COLUMNS = [
  {
    label: "Full Name",
    render: row => (
      <span style={{ fontWeight: 600, color: "#0f172a" }}>{row.full_name || "—"}</span>
    ),
  },
  {
    label: "Email",
    render: row => (
      <span style={{ fontSize: "0.83rem", color: "#475569" }}>{row.email || "—"}</span>
    ),
  },
  {
    label: "Document",
    render: row => (
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <Download size={14} color="#6366f1" style={{ flexShrink: 0 }} />
        <span
          title={row.document_name}
          style={{ fontSize: "0.83rem", color: "#334155" }}
        >
          {truncate(row.document_name, 38)}
        </span>
      </div>
    ),
  },
  {
    label: "Product",
    render: row => (
      <span style={{
        padding: "3px 10px", borderRadius: 20,
        background: "#f0f9ff", color: "#0284c7",
        fontSize: "0.73rem", fontWeight: 700,
        whiteSpace: "nowrap",
      }}>
        {row.product && row.product !== "—" ? row.product : "—"}
      </span>
    ),
  },
  {
    label: "Download Time",
    render: row => (
      <span style={{ fontSize: "0.82rem", color: "#64748b", whiteSpace: "nowrap" }}>
        {fmtDateTime(row.download_time)}
      </span>
    ),
  },
  {
    label: "OTP Verified",
    render: row => (
      <div style={{ display: "flex", justifyContent: "center" }}>
        <OtpCell value={row.otp_verified} />
      </div>
    ),
  },
  {
    label: "Status",
    render: row => <StatusBadge value={row.status} />,
  },
];

// ── Main component ────────────────────────────────────────────────────────────
export default function AdminDownloads() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off = 0) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/downloads", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  return (
    <AdminPageShell
      title="Downloads"
      description="Complete download request history. Tracks every download with OTP verification and status."
    >
      {/* Header */}
      <div style={{
        display:        "flex",
        alignItems:     "center",
        justifyContent: "space-between",
        marginBottom:   18,
        flexWrap:       "wrap",
        gap:            10,
      }}>
        <div style={{
          display: "flex", gap: 16, alignItems: "center", flexWrap: "wrap",
        }}>
          {/* Summary counts */}
          {[
            {
              label: "Total Requests",
              value: data.total,
              bg: "#f0f9ff", color: "#0284c7",
            },
            {
              label: "Completed",
              value: data.rows.filter(r => r.status === "Completed").length,
              bg: "#f0fdf4", color: "#15803d",
            },
            {
              label: "Pending OTP",
              value: data.rows.filter(r => r.status === "Pending OTP").length,
              bg: "#fef9c3", color: "#854d0e",
            },
          ].map(item => (
            <div key={item.label} style={{
              display:      "flex",
              alignItems:   "center",
              gap:          6,
              padding:      "5px 12px",
              borderRadius: 8,
              background:   item.bg,
              fontSize:     "0.78rem",
              fontWeight:   700,
              color:        item.color,
            }}>
              <span>{item.value}</span>
              <span style={{ fontWeight: 500 }}>{item.label}</span>
            </div>
          ))}
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
          background: "#fef2f2", border: "1px solid #fecaca",
          color: "#dc2626", borderRadius: 10,
          padding: "12px 16px", marginBottom: 18,
          fontSize: "0.875rem", fontWeight: 600,
        }}>
          ⚠ {error}
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
                {COLUMNS.map(col => (
                  <th key={col.label} style={{
                    padding:       "12px 16px",
                    textAlign:     col.label === "OTP Verified" ? "center" : "left",
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
                ? Array.from({ length: 6 }).map((_, i) => (
                  <SkeletonRow key={i} cols={COLUMNS.length} />
                ))
                : data.rows.length === 0
                  ? (
                    <tr>
                      <td colSpan={COLUMNS.length} style={{
                        padding:   "56px 16px",
                        textAlign: "center",
                        color:     "#94a3b8",
                        fontSize:  "0.9rem",
                      }}>
                        No downloads yet. Downloads are tracked automatically when users verify OTP.
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
                      {COLUMNS.map(col => (
                        <td key={col.label} style={{
                          padding:       "14px 16px",
                          verticalAlign: "middle",
                        }}>
                          {col.render(row)}
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
        @keyframes spin {
          from { transform: rotate(0deg); }
          to   { transform: rotate(360deg); }
        }
      `}</style>
    </AdminPageShell>
  );
}
