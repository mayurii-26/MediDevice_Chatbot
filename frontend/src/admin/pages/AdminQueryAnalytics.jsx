/**
 * AdminQueryAnalytics.jsx — Route: /admin/query-analytics
 * GET /admin/query-analytics?limit=20&offset=0
 *
 * Columns: Question, Intent, Times Asked, Last Asked, Answer Source
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import AdminTable     from "../components/AdminTable";

const PAGE_SIZE = 20;

const SOURCE_COLORS = {
  "Cache":          { bg: "#f0fdf4", color: "#16a34a" },
  "Knowledge Base": { bg: "#eff6ff", color: "#2563eb" },
  "Gemini":         { bg: "#faf5ff", color: "#7c3aed" },
  "Dynamic Search": { bg: "#fff7ed", color: "#ea580c" },
  "Fallback":       { bg: "#fef2f2", color: "#dc2626" },
};

function SourceBadge({ value }) {
  const s = SOURCE_COLORS[value] || { bg: "#f8fafc", color: "#475569" };
  return (
    <span style={{
      padding: "2px 10px", borderRadius: 20, fontSize: "0.75rem", fontWeight: 600,
      background: s.bg, color: s.color, whiteSpace: "nowrap",
    }}>
      {value || "—"}
    </span>
  );
}

function fmtDate(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch (_) { return val; }
}

const COLUMNS = [
  {
    key: "question", label: "Question",
    render: v => (
      <span title={v} style={{ maxWidth: 320, overflow: "hidden",
        textOverflow: "ellipsis", display: "block" }}>
        {v || "—"}
      </span>
    ),
  },
  {
    key: "intent", label: "Intent",
    render: v => (
      <span style={{
        padding: "2px 10px", borderRadius: 20, fontSize: "0.75rem",
        fontWeight: 600, background: "#f0f9ff", color: "#0284c7",
      }}>
        {v || "—"}
      </span>
    ),
  },
  {
    key: "times_asked", label: "Times Asked",
    render: v => (
      <span style={{ fontWeight: 700, color: "#0f172a" }}>{v ?? 0}</span>
    ),
  },
  { key: "last_asked",    label: "Last Asked",    render: fmtDate },
  { key: "answer_source", label: "Answer Source", render: v => <SourceBadge value={v} /> },
];

export default function AdminQueryAnalytics() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/query-analytics", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  return (
    <AdminPageShell
      title="Query Analytics"
      description="Questions asked, intent classification, and answer source breakdown."
    >
      <AdminTable
        columns={COLUMNS}
        rows={data.rows}
        total={data.total}
        limit={PAGE_SIZE}
        offset={offset}
        onPage={load}
        loading={loading}
        error={error}
      />
    </AdminPageShell>
  );
}
