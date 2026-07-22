/**
 * AdminConversations.jsx — Route: /admin/conversations
 * GET /admin/conversations?limit=20&offset=0
 *
 * Columns: Conversation ID, User, Start Time, Last Activity, Total Messages, Guest/User
 */
import { useEffect, useState, useCallback } from "react";
import { adminGetPaginated } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";
import AdminTable     from "../components/AdminTable";

const PAGE_SIZE = 20;

function fmtDate(val) {
  if (!val || val === "—") return "—";
  try {
    return new Date(val).toLocaleString("en-IN", {
      day: "2-digit", month: "short", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  } catch (_) { return val; }
}

function shortId(id) {
  if (!id || id === "—") return "—";
  return (
    <span title={id} style={{ fontFamily: "monospace", fontSize: "0.78rem", color: "#475569" }}>
      {id.slice(0, 8)}…
    </span>
  );
}

const COLUMNS = [
  { key: "id",             label: "Conversation ID", render: shortId },
  {
    key: "user_id", label: "User ID",
    render: v => v === "—" ? (
      <span style={{ color: "#94a3b8" }}>Guest</span>
    ) : (
      <span title={v} style={{ fontFamily: "monospace", fontSize: "0.78rem" }}>
        {v.slice(0, 8)}…
      </span>
    ),
  },
  { key: "start_time",    label: "Start Time",    render: fmtDate },
  { key: "last_activity", label: "Last Activity", render: fmtDate },
  {
    key: "total_messages", label: "Messages",
    render: v => (
      <span style={{
        display: "inline-block", padding: "2px 10px", borderRadius: 20,
        background: "#f0f9ff", color: "#0284c7",
        fontWeight: 700, fontSize: "0.82rem",
      }}>
        {v ?? 0}
      </span>
    ),
  },
  {
    key: "user_type", label: "Type",
    render: v => {
      const isReg = v === "Registered";
      return (
        <span style={{
          padding: "2px 10px", borderRadius: 20, fontSize: "0.75rem", fontWeight: 600,
          background: isReg ? "#f0fdf4" : "#f8fafc",
          color:      isReg ? "#16a34a" : "#64748b",
        }}>
          {v}
        </span>
      );
    },
  },
];

export default function AdminConversations() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/conversations", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  return (
    <AdminPageShell
      title="Conversations"
      description="All chatbot conversation sessions with message counts and activity timestamps."
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
