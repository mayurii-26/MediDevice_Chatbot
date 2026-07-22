/**
 * AdminDashboard.jsx — Route: /admin/dashboard
 * Fetches real stats from GET /admin/dashboard/stats
 */
import { useEffect, useState } from "react";
import { adminGet } from "../lib/adminApi";
import AdminPageShell from "../components/AdminPageShell";

const CARDS = [
  { key: "total_users",      label: "Total Users",       icon: "👥", color: "#0ea5e9" },
  { key: "registered_users", label: "Registered Users",  icon: "🧑‍💼", color: "#6366f1" },
  { key: "guest_users",      label: "Guest Users",       icon: "👤", color: "#8b5cf6" },
  { key: "total_queries",    label: "Total Queries",     icon: "💬", color: "#10b981" },
  { key: "today_queries",    label: "Today's Queries",   icon: "📈", color: "#f59e0b" },
  { key: "total_downloads",  label: "Total Downloads",   icon: "📥", color: "#ef4444" },
  { key: "total_documents",  label: "Total Documents",   icon: "📄", color: "#14b8a6" },
];

export default function AdminDashboard() {
  const [stats,   setStats]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  useEffect(() => {
    adminGet("/admin/dashboard/stats")
      .then(setStats)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <AdminPageShell
      title="Dashboard"
      description="Real-time overview of system activity and key metrics."
    >
      {loading && (
        <div style={{ color: "#64748b", fontSize: "0.9rem", padding: "16px 0" }}>
          Loading stats…
        </div>
      )}
      {error && (
        <div style={{
          background: "#fef2f2", border: "1px solid #fca5a5",
          borderRadius: 10, padding: "12px 16px",
          color: "#dc2626", fontSize: "0.85rem", marginBottom: 16,
        }}>
          {error}
        </div>
      )}
      {stats && (
        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(auto-fill, minmax(190px, 1fr))",
          gap: 16,
          marginTop: 8,
        }}>
          {CARDS.map(({ key, label, icon, color }) => (
            <StatCard
              key={key}
              label={label}
              value={stats[key] ?? 0}
              icon={icon}
              color={color}
            />
          ))}
        </div>
      )}
    </AdminPageShell>
  );
}

function StatCard({ label, value, icon, color }) {
  return (
    <div style={{
      background: "#fff",
      border: "1px solid #e2e8f0",
      borderRadius: 14,
      padding: "22px 20px",
      boxShadow: "0 1px 4px rgba(0,0,0,0.05)",
      display: "flex",
      flexDirection: "column",
      gap: 10,
    }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span style={{ fontSize: "1.4rem" }}>{icon}</span>
        <div style={{
          width: 8, height: 8, borderRadius: "50%", background: color,
        }} />
      </div>
      <div>
        <div style={{
          fontSize: "2rem", fontWeight: 900, color: "#0f172a", lineHeight: 1,
        }}>
          {value.toLocaleString()}
        </div>
        <div style={{
          fontSize: "0.75rem", fontWeight: 600, color: "#94a3b8",
          textTransform: "uppercase", letterSpacing: "0.05em", marginTop: 6,
        }}>
          {label}
        </div>
      </div>
    </div>
  );
}
