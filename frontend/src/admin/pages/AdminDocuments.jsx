/**
 * AdminDocuments.jsx — Route: /admin/documents
 * GET /admin/documents?limit=20&offset=0
 *
 * Columns: Document Name, Download Count, Unique Users, Last Download
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

const COLUMNS = [
  {
    key: "document_name", label: "Document Name",
    render: v => (
      <span title={v} style={{ fontWeight: 600, color: "#0f172a" }}>
        {v || "—"}
      </span>
    ),
  },
  {
    key: "download_count", label: "Downloads",
    render: v => (
      <span style={{
        display: "inline-block", padding: "2px 12px", borderRadius: 20,
        background: "#eff6ff", color: "#2563eb",
        fontWeight: 700, fontSize: "0.82rem",
      }}>
        {v ?? 0}
      </span>
    ),
  },
  {
    key: "unique_users", label: "Unique Users",
    render: v => (
      <span style={{ fontWeight: 600, color: "#059669" }}>{v ?? 0}</span>
    ),
  },
  { key: "last_download", label: "Last Download", render: fmtDate },
];

export default function AdminDocuments() {
  const [data,    setData]    = useState({ rows: [], total: 0 });
  const [offset,  setOffset]  = useState(0);
  const [loading, setLoading] = useState(false);
  const [error,   setError]   = useState("");

  const load = useCallback((off) => {
    setLoading(true);
    setError("");
    adminGetPaginated("/admin/documents", { limit: PAGE_SIZE, offset: off })
      .then(d => { setData(d); setOffset(off); })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(0); }, [load]);

  return (
    <AdminPageShell
      title="Documents"
      description="Document download counts, unique users, and last download time."
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
