/**
 * AdminAIAnalytics.jsx — Route: /admin/ai-analytics
 * GET /admin/ai-analytics
 *
 * Displays response type breakdown in a professional table.
 * Columns: Response Type, Count, Percentage
 */
import { useEffect, useState } from "react";
import { adminGet } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";

const TYPE_ICONS = {
  "Knowledge Base Responses":    "🗃️",
  "Cache Responses":             "⚡",
  "Gemini Responses":            "✨",
  "Dynamic Search Responses":    "🌐",
  "Medical Formatter Responses": "🏥",
  "Fallback Responses":          "⚠️",
};

const TYPE_COLORS = {
  "Knowledge Base Responses":    { bg: "#eff6ff", bar: "#3b82f6" },
  "Cache Responses":             { bg: "#f0fdf4", bar: "#22c55e" },
  "Gemini Responses":            { bg: "#faf5ff", bar: "#a855f7" },
  "Dynamic Search Responses":    { bg: "#fff7ed", bar: "#f97316" },
  "Medical Formatter Responses": { bg: "#f0fdfa", bar: "#14b8a6" },
  "Fallback Responses":          { bg: "#fef2f2", bar: "#ef4444" },
};

export default function AdminAIAnalytics() {
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  useEffect(() => {
    adminGet("/admin/ai-analytics")
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const rows  = data?.rows          || [];
  const total = data?.total_queries || 0;

  return (
    <AdminPageShell
      title="AI Analytics"
      description="Response pipeline breakdown by answer source type."
    >
      {/* Summary strip */}
      <div style={{
        background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
        padding: "16px 24px", marginBottom: 20,
        display: "flex", alignItems: "center", gap: 8,
        boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
      }}>
        <span style={{ fontSize: "1.1rem" }}>📊</span>
        <span style={{ fontWeight: 700, color: "#0f172a", fontSize: "0.95rem" }}>
          Total Queries Logged:
        </span>
        <span style={{ fontWeight: 900, color: "#0ea5e9", fontSize: "1.1rem" }}>
          {total.toLocaleString()}
        </span>
      </div>

      {loading && (
        <div style={{ color: "#64748b", fontSize: "0.9rem" }}>Loading…</div>
      )}
      {error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fca5a5", borderRadius: 10,
          padding: "12px 16px", color: "#dc2626", fontSize: "0.85rem",
        }}>
          {error}
        </div>
      )}

      {!loading && !error && (
        <div style={{
          background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
          overflow: "hidden", boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}>
          <table style={{ width: "100%", borderCollapse: "collapse" }}>
            <thead>
              <tr style={{ background: "#f8fafc" }}>
                {["Response Type", "Count", "Share", "Distribution"].map(h => (
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
              {rows.map((row, i) => {
                const c    = TYPE_COLORS[row.response_type] || { bg: "#f8fafc", bar: "#94a3b8" };
                const icon = TYPE_ICONS[row.response_type]  || "📌";
                const pct  = parseFloat(row.percentage) || 0;
                return (
                  <tr key={i} style={{ borderBottom: "1px solid #f1f5f9" }}
                    onMouseEnter={e => { e.currentTarget.style.background = "#f8fafc"; }}
                    onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
                  >
                    {/* Type */}
                    <td style={{ padding: "13px 20px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                        <div style={{
                          background: c.bg, borderRadius: 8,
                          padding: "4px 8px", fontSize: "1rem",
                        }}>
                          {icon}
                        </div>
                        <span style={{ fontWeight: 600, color: "#0f172a", fontSize: "0.88rem" }}>
                          {row.response_type}
                        </span>
                      </div>
                    </td>
                    {/* Count */}
                    <td style={{ padding: "13px 20px" }}>
                      <span style={{ fontWeight: 800, color: "#0f172a", fontSize: "1.1rem" }}>
                        {row.count.toLocaleString()}
                      </span>
                    </td>
                    {/* Percentage */}
                    <td style={{ padding: "13px 20px" }}>
                      <span style={{
                        padding: "3px 10px", borderRadius: 20, fontSize: "0.8rem",
                        fontWeight: 700, background: c.bg, color: c.bar,
                      }}>
                        {row.percentage}
                      </span>
                    </td>
                    {/* Bar */}
                    <td style={{ padding: "13px 20px", minWidth: 180 }}>
                      <div style={{
                        height: 8, borderRadius: 4, background: "#f1f5f9", overflow: "hidden",
                      }}>
                        <div style={{
                          height: "100%", width: `${Math.min(pct, 100)}%`,
                          background: c.bar, borderRadius: 4,
                          transition: "width 0.4s ease",
                        }} />
                      </div>
                    </td>
                  </tr>
                );
              })}
              {rows.length === 0 && (
                <tr>
                  <td colSpan={4} style={{
                    padding: "48px 20px", textAlign: "center",
                    color: "#94a3b8", fontSize: "0.9rem",
                  }}>
                    No query logs found.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}
    </AdminPageShell>
  );
}
