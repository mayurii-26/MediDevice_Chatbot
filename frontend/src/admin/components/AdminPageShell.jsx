/**
 * AdminPageShell.jsx
 * Shared page wrapper — consistent header + content area for every admin page.
 *
 * Props:
 *   title       {string}
 *   description {string}
 *   children    {ReactNode}
 */
export default function AdminPageShell({ title, description, children }) {
  return (
    <div style={{ minHeight: "100vh", background: "#f8fafc" }}>
      <div style={{
        padding: "28px 32px 0",
        borderBottom: "1px solid #e2e8f0",
        background: "#fff",
      }}>
        <h1 style={{ fontSize: "1.4rem", fontWeight: 800, color: "#0f172a", margin: 0 }}>
          {title}
        </h1>
        {description && (
          <p style={{ fontSize: "0.85rem", color: "#64748b", marginTop: 4, marginBottom: 20 }}>
            {description}
          </p>
        )}
      </div>
      <div style={{ padding: "24px 32px 40px" }}>
        {children}
      </div>
    </div>
  );
}
