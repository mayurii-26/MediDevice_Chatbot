/**
 * AdminUsers.jsx — Route: /admin/users
 *
 * TOP:   4 live stat cards  (GET /admin/users/stats)
 * BELOW: Full paginated users table (GET /admin/users)
 *
 * Both sections coexist — nothing removed.
 */
import { useEffect, useState, useCallback } from "react";
import { adminGet, adminGetPaginated } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import AdminTable     from "../components/AdminTable";
import { Users, UserCheck, Activity, MessageSquare, RefreshCw } from "lucide-react";

const PAGE_SIZE = 20;

// ── Card config ──────────────────────────────────────────────────────────────
const CARD_CONFIG = [
  {
    key: "total_registered", label: "Total Registered Users",
    icon: UserCheck,
    gradient: "linear-gradient(135deg,#6366f1,#818cf8)",
    shadowColor: "rgba(99,102,241,0.35)", bg: "#f0f0ff", iconColor: "#6366f1",
  },
  {
    key: "guest_users", label: "Guest Users",
    icon: Users,
    gradient: "linear-gradient(135deg,#f59e0b,#fbbf24)",
    shadowColor: "rgba(245,158,11,0.35)", bg: "#fffbeb", iconColor: "#d97706",
  },
  {
    key: "active_today", label: "Active Users Today",
    icon: Activity,
    gradient: "linear-gradient(135deg,#10b981,#34d399)",
    shadowColor: "rgba(16,185,129,0.35)", bg: "#f0fdf4", iconColor: "#059669",
  },
  {
    key: "total_conversations", label: "Total Conversations",
    icon: MessageSquare,
    gradient: "linear-gradient(135deg,#0ea5e9,#38bdf8)",
    shadowColor: "rgba(14,165,233,0.35)", bg: "#f0f9ff", iconColor: "#0284c7",
  },
];

// ── Helpers ──────────────────────────────────────────────────────────────────
function formatNumber(n) {
  if (n === undefined || n === null) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `${(n / 1_000).toFixed(1)}K`;
  return String(n);
}

function fmtDate(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleDateString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
    });
  } catch (_) { return val; }
}

function shortId(id) {
  if (!id || id === "—") return "—";
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

function NumBadge({ value, color }) {
  return (
    <span style={{
      display: "inline-block", padding: "2px 10px", borderRadius: 20,
      fontSize: "0.78rem", fontWeight: 700,
      background: `${color}18`, color,
      minWidth: 28, textAlign: "center",
    }}>
      {value ?? 0}
    </span>
  );
}

// ── Stat card ────────────────────────────────────────────────────────────────
function StatCard({ config, value, loading }) {
  const Icon = config.icon;
  return (
    <div style={{
      background: "#fff", border: "1px solid #e2e8f0", borderRadius: 16,
      padding: "28px 28px 24px",
      boxShadow: `0 4px 24px ${config.shadowColor}`,
      display: "flex", flexDirection: "column", gap: 12,
      position: "relative", overflow: "hidden",
      flex: "1 1 200px", minWidth: 200,
    }}>
      <div style={{
        position: "absolute", top: -20, right: -20,
        width: 100, height: 100, borderRadius: "50%",
        background: config.gradient, opacity: 0.08,
      }} />
      <div style={{
        width: 44, height: 44, borderRadius: 12, background: config.bg,
        display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      }}>
        <Icon size={22} color={config.iconColor} strokeWidth={2} />
      </div>
      <div style={{ fontSize: "2.4rem", fontWeight: 800, color: "#0f172a", lineHeight: 1 }}>
        {loading ? (
          <span style={{
            display: "inline-block", width: 64, height: 36,
            background: "#f1f5f9", borderRadius: 8,
            animation: "pulse 1.4s ease-in-out infinite",
          }} />
        ) : formatNumber(value)}
      </div>
      <div style={{ fontSize: "0.82rem", fontWeight: 600, color: "#64748b", letterSpacing: "0.02em" }}>
        {config.label}
      </div>
      <div style={{
        position: "absolute", bottom: 0, left: 0, right: 0, height: 3,
        background: config.gradient, borderRadius: "0 0 16px 16px",
      }} />
    </div>
  );
}

// ── Table columns ────────────────────────────────────────────────────────────
const TABLE_COLUMNS = [
  {
    key: "user_id", label: "User ID",
    render: v => (
      <span title={v} style={{ fontFamily: "monospace", fontSize: "0.78rem", color: "#475569" }}>
        {shortId(v)}
      </span>
    ),
  },
  { key: "email",               label: "Email",         render: v => v || "—" },
  { key: "signup_date",         label: "Signup Date",   render: fmtDate },
  { key: "last_login",          label: "Last Login",    render: fmtDate },
  { key: "total_conversations", label: "Conversations", render: v => <NumBadge value={v} color="#6366f1" /> },
  { key: "total_queries",       label: "Queries",       render: v => <NumBadge value={v} color="#10b981" /> },
  { key: "documents_downloaded",label: "Downloads",     render: v => <NumBadge value={v} color="#0ea5e9" /> },
];

// ── Main ─────────────────────────────────────────────────────────────────────
export default function AdminUsers() {
  const [stats,        setStats]        = useState(null);
  const [statsLoading, setStatsLoading] = useState(false);
  const [statsError,   setStatsError]   = useState("");
  const [lastFetched,  setLastFetched]  = useState(null);

  const [tableData,    setTableData]    = useState({ rows: [], total: 0 });
  const [tableOffset,  setTableOffset]  = useState(0);
  const [tableLoading, setTableLoading] = useState(false);
  const [tableError,   setTableError]   = useState("");

  function loadStats() {
    setStatsLoading(true);
    setStatsError("");
    adminGet("/admin/users/stats")
      .then(d => { setStats(d); setLastFetched(new Date()); })
      .catch(e => setStatsError(e.message))
      .finally(() => setStatsLoading(false));
  }

  const loadTable = useCallback((off = 0) => {
    setTableLoading(true);
    setTableError("");
    adminGetPaginated("/admin/users", { limit: PAGE_SIZE, offset: off })
      .then(d => { setTableData(d); setTableOffset(off); })
      .catch(e => setTableError(e.message))
      .finally(() => setTableLoading(false));
  }, []);

  useEffect(() => { loadStats(); loadTable(0); }, [loadTable]);

  return (
    <AdminPageShell title="Users" description="Live overview of user activity across the platform.">

      {/* Toolbar */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginBottom: 20, flexWrap: "wrap", gap: 12,
      }}>
        <span style={{ fontSize: "0.82rem", color: "#94a3b8" }}>
          {lastFetched ? `Last updated: ${lastFetched.toLocaleTimeString("en-IN")}` : "Fetching live data…"}
        </span>
        <button
          onClick={() => { loadStats(); loadTable(0); }}
          disabled={statsLoading || tableLoading}
          style={{
            display: "flex", alignItems: "center", gap: 6,
            padding: "7px 16px", borderRadius: 8, border: "1.5px solid #e2e8f0",
            background: "#fff", color: "#475569", fontSize: "0.82rem", fontWeight: 600,
            cursor: "pointer", opacity: (statsLoading || tableLoading) ? 0.6 : 1,
          }}
        >
          <RefreshCw size={14} style={{ animation: (statsLoading || tableLoading) ? "spin 0.7s linear infinite" : "none" }} />
          Refresh
        </button>
      </div>

      {statsError && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fecaca", color: "#dc2626",
          borderRadius: 10, padding: "12px 16px", marginBottom: 20,
          fontSize: "0.875rem", fontWeight: 600,
        }}>⚠ {statsError}</div>
      )}

      {/* ── Stat cards ── */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 20, marginBottom: 40 }}>
        {CARD_CONFIG.map(cfg => (
          <StatCard key={cfg.key} config={cfg} value={stats ? stats[cfg.key] : undefined} loading={statsLoading} />
        ))}
      </div>

      {/* ── Section heading ── */}
      <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16 }}>
        <span style={{ fontSize: "0.95rem", fontWeight: 700, color: "#1e293b", display: "flex", alignItems: "center", gap: 7 }}>
          <Users size={16} color="#6366f1" /> All Users
        </span>
        <div style={{ flex: 1, height: 1, background: "#e2e8f0" }} />
        <span style={{ fontSize: "0.78rem", color: "#94a3b8" }}>{tableData.total} total</span>
      </div>

      {/* ── Users table ── */}
      <AdminTable
        columns={TABLE_COLUMNS}
        rows={tableData.rows}
        total={tableData.total}
        limit={PAGE_SIZE}
        offset={tableOffset}
        onPage={loadTable}
        loading={tableLoading}
        error={tableError}
      />

      <style>{`
        @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }
        @keyframes spin  { from{transform:rotate(0deg)} to{transform:rotate(360deg)} }
      `}</style>
    </AdminPageShell>
  );
}
