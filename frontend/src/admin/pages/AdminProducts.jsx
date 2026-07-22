/**
 * AdminProducts.jsx — Route: /admin/products
 *
 * TOP:   Top 5 Most Queried Products     (GET /admin/products?limit=5)
 *        Source: query_logs analytics
 *        Columns: Rank | Product | Total Queries (bar) | Last Asked
 *
 * BELOW: All Products — Complete Knowledge Base Catalog  (GET /admin/products/catalog)
 *        Source: device_documents table (ALL 34 products)
 *        Columns: Product | Category | Total | General | Spec | Feature | Comparison | Last Asked
 *        Products never queried show with 0 counts.
 *
 * These are TWO different data sources. Both sections always visible.
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import AdminTable     from "../components/AdminTable";
import { BarChart2, Clock, RefreshCw, TrendingUp, Database } from "lucide-react";

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

// ── Rank medal styles ────────────────────────────────────────────────────────
const RANK_STYLES = [
  { bg: "#fef9c3", color: "#854d0e", label: "🥇" },
  { bg: "#f1f5f9", color: "#334155", label: "🥈" },
  { bg: "#fff7ed", color: "#9a3412", label: "🥉" },
  { bg: "#f0fdf4", color: "#166534", label: "4"  },
  { bg: "#f0f9ff", color: "#0369a1", label: "5"  },
];

// ── Query bar ────────────────────────────────────────────────────────────────
function QueryBar({ value, max }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 130 }}>
      <div style={{ flex: 1, height: 8, background: "#f1f5f9", borderRadius: 99, overflow: "hidden" }}>
        <div style={{
          width: `${pct}%`, height: "100%",
          background: "linear-gradient(90deg,#6366f1,#0ea5e9)",
          borderRadius: 99, transition: "width 0.6s ease",
        }} />
      </div>
      <span style={{ fontWeight: 800, color: "#0f172a", fontSize: "0.95rem", minWidth: 24 }}>{value}</span>
    </div>
  );
}

// ── Skeleton row ─────────────────────────────────────────────────────────────
function SkeletonRow({ cols = 4 }) {
  return (
    <tr>
      {Array.from({ length: cols }).map((_, i) => (
        <td key={i} style={{ padding: "12px 14px" }}>
          <div style={{
            height: 14, background: "#f1f5f9", borderRadius: 5,
            width: i === 1 ? "70%" : "40%",
            animation: "pulse 1.4s ease-in-out infinite",
          }} />
        </td>
      ))}
    </tr>
  );
}

// ── Catalog table count badge ────────────────────────────────────────────────
function CountBadge({ value, color = "#64748b" }) {
  const n = value ?? 0;
  if (n === 0) return <span style={{ color: "#cbd5e1", fontSize: "0.82rem" }}>—</span>;
  return (
    <span style={{
      display: "inline-block", padding: "2px 8px", borderRadius: 12,
      fontSize: "0.78rem", fontWeight: 700,
      background: `${color}18`, color,
    }}>{n}</span>
  );
}

// ── Catalog table columns (All Products from knowledge base) ─────────────────
const CATALOG_COLS = [
  {
    key: "product_name", label: "Product",
    render: v => <span style={{ fontWeight: 600, color: "#0f172a", fontSize: "0.875rem" }}>{v || "—"}</span>,
  },
  {
    key: "category", label: "Category",
    render: v => (
      <span style={{
        display: "inline-block", padding: "2px 8px", borderRadius: 10,
        background: "#e0f2fe", color: "#0369a1", fontSize: "0.72rem", fontWeight: 700,
      }}>{v || "—"}</span>
    ),
  },
  {
    key: "total_queries", label: "Total",
    render: v => <CountBadge value={v} color="#0284c7" />,
  },
  {
    key: "general_queries", label: "General",
    render: v => <CountBadge value={v} color="#6366f1" />,
  },
  {
    key: "specification_queries", label: "Spec",
    render: v => <CountBadge value={v} color="#059669" />,
  },
  {
    key: "feature_queries", label: "Features",
    render: v => <CountBadge value={v} color="#d97706" />,
  },
  {
    key: "comparison_queries", label: "Compare",
    render: v => <CountBadge value={v} color="#7c3aed" />,
  },
  {
    key: "last_asked", label: "Last Asked",
    render: v => (
      <span style={{ fontSize: "0.78rem", color: "#64748b" }}>
        {v && v !== "—" ? fmtDateTime(v) : <span style={{ color: "#cbd5e1" }}>Never</span>}
      </span>
    ),
  },
];

// ── Main ─────────────────────────────────────────────────────────────────────
export default function AdminProducts() {
  // Top-5 state
  const [top5,        setTop5]        = useState([]);
  const [top5Loading, setTop5Loading] = useState(false);
  const [top5Error,   setTop5Error]   = useState("");

  // Catalog table state (device_documents = knowledge base)
  const [catData,    setCatData]    = useState({ rows: [], total: 0 });
  const [catOffset,  setCatOffset]  = useState(0);
  const [catLoading, setCatLoading] = useState(false);
  const [catError,   setCatError]   = useState("");

  function loadTop5() {
    setTop5Loading(true);
    setTop5Error("");
    adminGetPaginated("/admin/products", { limit: 5, offset: 0 })
      .then(d => setTop5(d.rows || []))
      .catch(e => setTop5Error(e.message))
      .finally(() => setTop5Loading(false));
  }

  const loadCatalog = useCallback((off = 0) => {
    setCatLoading(true);
    setCatError("");
    adminGetPaginated("/admin/products/catalog", { limit: PAGE_SIZE, offset: off })
      .then(d => { setCatData(d); setCatOffset(off); })
      .catch(e => setCatError(e.message))
      .finally(() => setCatLoading(false));
  }, []);

  useEffect(() => { loadTop5(); loadCatalog(0); }, [loadCatalog]);

  const maxQ = top5.length ? Math.max(...top5.map(r => r.total_queries || 0)) : 1;

  return (
    <AdminPageShell
      title="Products"
      description="Top queried products (analytics) and complete product knowledge base catalog."
    >
      {/* ── Toolbar ── */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 20, flexWrap: "wrap", gap: 12,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <TrendingUp size={16} color="#6366f1" />
          <span style={{ fontSize: "0.82rem", color: "#64748b", fontWeight: 600 }}>
            Counts every query type: general, comparison, specification, features
          </span>
        </div>
        <button
          onClick={() => { loadTop5(); loadCatalog(0); }}
          disabled={top5Loading || catLoading}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "7px 16px", borderRadius: 8, border: "1.5px solid #e2e8f0",
            background: "#fff", color: "#475569", fontSize: "0.82rem", fontWeight: 600,
            cursor: "pointer", opacity: (top5Loading || catLoading) ? 0.6 : 1,
          }}
        >
          <RefreshCw size={14} style={{ animation: (top5Loading || catLoading) ? "spin 0.7s linear infinite" : "none" }} />
          Refresh
        </button>
      </div>

      {top5Error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
          borderRadius: 10, padding: "12px 16px", marginBottom: 16,
          fontSize: "0.875rem", fontWeight: 600,
        }}>⚠ {top5Error}</div>
      )}

      {/* ══ TOP 5 SECTION — Analytics source ══════════════════════════════ */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
        <span style={{
          fontSize: "0.95rem", fontWeight: 700, color: "#1e293b",
          display: "flex", alignItems: "center", gap: 7,
        }}>
          <TrendingUp size={16} color="#6366f1" /> Top 5 Most Queried Products
        </span>
        <div style={{ flex: 1, height: 1, background: "#e2e8f0" }} />
        <span style={{
          fontSize: "0.7rem", fontWeight: 600, color: "#0284c7",
          background: "#e0f2fe", padding: "2px 8px", borderRadius: 8,
        }}>Source: Analytics</span>
      </div>

      <div style={{
        background: "#fff", border: "1px solid #e2e8f0", borderRadius: 14,
        overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.05)", marginBottom: 40,
      }}>
        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc", borderBottom: "1px solid #e2e8f0" }}>
              {[
                { label: "#", w: "5%" },
                { label: "Product", w: "38%" },
                { label: "Total Queries", w: "32%", Icon: BarChart2 },
                { label: "Last Asked", w: "25%", Icon: Clock },
              ].map(col => (
                <th key={col.label} style={{
                  padding: "13px 18px", textAlign: "left",
                  fontSize: "0.72rem", fontWeight: 700, color: "#64748b",
                  textTransform: "uppercase", letterSpacing: "0.06em", width: col.w,
                }}>
                  <span style={{ display: "flex", alignItems: "center", gap: 5 }}>
                    {col.Icon && <col.Icon size={12} />}{col.label}
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {top5Loading
              ? Array.from({ length: 5 }).map((_, i) => <SkeletonRow key={i} cols={4} />)
              : top5.length === 0
                ? (
                  <tr>
                    <td colSpan={4} style={{ padding: "48px 16px", textAlign: "center", color: "#94a3b8", fontSize: "0.9rem" }}>
                      No product queries recorded yet. Start a conversation with the chatbot!
                    </td>
                  </tr>
                )
                : top5.map((row, idx) => {
                  const rank = RANK_STYLES[idx] || RANK_STYLES[4];
                  return (
                    <tr key={row.product}
                      style={{ borderBottom: idx < top5.length - 1 ? "1px solid #f1f5f9" : "none" }}
                      onMouseEnter={e => e.currentTarget.style.background = "#fafafa"}
                      onMouseLeave={e => e.currentTarget.style.background = ""}
                    >
                      <td style={{ padding: "16px 18px" }}>
                        <span style={{
                          display: "inline-flex", alignItems: "center", justifyContent: "center",
                          width: 30, height: 30, borderRadius: 8,
                          background: rank.bg, color: rank.color,
                          fontSize: idx < 3 ? "1rem" : "0.8rem", fontWeight: 700,
                        }}>{rank.label}</span>
                      </td>
                      <td style={{ padding: "16px 18px" }}>
                        <span style={{ fontWeight: 700, color: "#0f172a", fontSize: "0.9rem" }}>{row.product || "—"}</span>
                      </td>
                      <td style={{ padding: "16px 18px" }}>
                        <QueryBar value={row.total_queries || 0} max={maxQ} />
                      </td>
                      <td style={{ padding: "16px 18px" }}>
                        <span style={{ fontSize: "0.82rem", color: "#64748b" }}>{fmtDateTime(row.last_asked)}</span>
                      </td>
                    </tr>
                  );
                })
            }
          </tbody>
        </table>
      </div>

      {/* ══ ALL PRODUCTS SECTION — Knowledge Base source ══════════════════ */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <span style={{
          fontSize: "0.95rem", fontWeight: 700, color: "#1e293b",
          display: "flex", alignItems: "center", gap: 7,
        }}>
          <Database size={16} color="#0284c7" /> All Products
        </span>
        <div style={{ flex: 1, height: 1, background: "#e2e8f0" }} />
        <span style={{
          fontSize: "0.7rem", fontWeight: 600, color: "#059669",
          background: "#f0fdf4", padding: "2px 8px", borderRadius: 8,
        }}>Source: Knowledge Base</span>
        <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{catData.total} products</span>
      </div>

      {catError && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
          borderRadius: 10, padding: "12px 16px", marginBottom: 16,
          fontSize: "0.875rem", fontWeight: 600,
        }}>⚠ {catError}</div>
      )}

      <AdminTable
        columns={CATALOG_COLS}
        rows={catData.rows}
        total={catData.total}
        limit={PAGE_SIZE}
        offset={catOffset}
        onPage={loadCatalog}
        loading={catLoading}
        error={catError}
      />

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </AdminPageShell>
  );
}
