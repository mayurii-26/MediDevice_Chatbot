import AdminPageShell from "../components/AdminPageShell";

export default function AdminSettings() {
  return (
    <AdminPageShell
      title="Settings"
      description="Admin portal configuration, credentials, and feature flags."
    >
      <SettingsPlaceholder sections={[
        "Admin Credentials",
        "Cache Control",
        "Feature Flags",
        "Email Notifications",
        "API Keys",
      ]} />
    </AdminPageShell>
  );
}

function SettingsPlaceholder({ sections }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {sections.map(label => (
        <div key={label} style={{
          background: "#fff", border: "1px solid #e2e8f0", borderRadius: 12,
          padding: "18px 20px", display: "flex", alignItems: "center",
          justifyContent: "space-between", boxShadow: "0 1px 3px rgba(0,0,0,0.05)",
        }}>
          <span style={{ fontSize: "0.9rem", fontWeight: 600, color: "#0f172a" }}>{label}</span>
          <span style={{
            fontSize: "0.75rem", fontWeight: 500, color: "#94a3b8",
            background: "#f1f5f9", padding: "3px 10px", borderRadius: 10,
          }}>
            Coming soon
          </span>
        </div>
      ))}
    </div>
  );
}
