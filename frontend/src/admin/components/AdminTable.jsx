/**
 * AdminTable.jsx
 *
 * Reusable table with built-in pagination controls.
 *
 * Props:
 *   columns   {Array<{key, label, render?}>}  — column definitions
 *   rows      {Array<object>}                 — data rows
 *   total     {number}                        — total row count (for pagination)
 *   limit     {number}                        — rows per page
 *   offset    {number}                        — current offset
 *   onPage    {(newOffset) => void}           — called when page changes
 *   loading   {boolean}
 *   error     {string|null}
 */
export default function AdminTable({
  columns, rows, total, limit, offset, onPage, loading, error,
}) {
  const page      = Math.floor(offset / limit) + 1;
  const totalPages = Math.max(1, Math.ceil(total / limit));
  const from      = total === 0 ? 0 : offset + 1;
  const to        = Math.min(offset + limit, total);

  return (
    <div>
      {/* Table card */}
      <div style={{
        background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
        overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}>
        {/* Loading / error banners */}
        {loading && (
          <div style={{ padding: "14px 20px", borderBottom: "1px solid #e2e8f0",
            fontSize: "0.85rem", color: "#0284c7", background: "#f0f9ff" }}>
            Loading…
          </div>
        )}
        {error && (
          <div style={{ padding: "14px 20px", borderBottom: "1px solid #fca5a5",
            fontSize: "0.85rem", color: "#dc2626", background: "#fef2f2" }}>
            {error}
          </div>
        )}

        <table style={{ width: "100%", borderCollapse: "collapse" }}>
          <thead>
            <tr style={{ background: "#f8fafc" }}>
              {columns.map(col => (
                <th key={col.key} style={{
                  padding: "11px 16px", textAlign: "left",
                  fontSize: "0.72rem", fontWeight: 700, color: "#64748b",
                  textTransform: "uppercase", letterSpacing: "0.05em",
                  borderBottom: "1px solid #e2e8f0", whiteSpace: "nowrap",
                }}>
                  {col.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {!loading && rows.length === 0 ? (
              <tr>
                <td colSpan={columns.length} style={{
                  padding: "48px 16px", textAlign: "center",
                  color: "#94a3b8", fontSize: "0.9rem",
                }}>
                  No data found.
                </td>
              </tr>
            ) : (
              rows.map((row, i) => (
                <tr key={i} style={{
                  borderBottom: "1px solid #f1f5f9",
                  transition: "background 0.1s",
                }}
                  onMouseEnter={e => { e.currentTarget.style.background = "#f8fafc"; }}
                  onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                >
                  {columns.map(col => (
                    <td key={col.key} style={{
                      padding: "11px 16px", fontSize: "0.85rem",
                      color: "#374151", maxWidth: 300,
                      overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                    }}>
                      {col.render ? col.render(row[col.key], row) : (row[col.key] ?? "—")}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Pagination footer */}
      <div style={{
        display: "flex", alignItems: "center", justifyContent: "space-between",
        marginTop: 16, padding: "0 4px",
      }}>
        <span style={{ fontSize: "0.8rem", color: "#64748b" }}>
          {total === 0 ? "No results" : `Showing ${from}–${to} of ${total}`}
        </span>
        <div style={{ display: "flex", gap: 8 }}>
          <PageBtn
            label="← Prev"
            disabled={offset === 0 || loading}
            onClick={() => onPage(Math.max(0, offset - limit))}
          />
          <span style={{
            padding: "6px 14px", fontSize: "0.8rem", color: "#374151",
            background: "#fff", border: "1px solid #e2e8f0", borderRadius: 8,
          }}>
            {page} / {totalPages}
          </span>
          <PageBtn
            label="Next →"
            disabled={offset + limit >= total || loading}
            onClick={() => onPage(offset + limit)}
          />
        </div>
      </div>
    </div>
  );
}

function PageBtn({ label, disabled, onClick }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding: "6px 14px", fontSize: "0.8rem", fontWeight: 600,
        background: disabled ? "#f1f5f9" : "#0ea5e9",
        color: disabled ? "#94a3b8" : "#fff",
        border: "none", borderRadius: 8,
        cursor: disabled ? "not-allowed" : "pointer",
        transition: "background 0.15s",
      }}
    >
      {label}
    </button>
  );
}
