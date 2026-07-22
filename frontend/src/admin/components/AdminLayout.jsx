/**
 * AdminLayout.jsx
 *
 * Persistent shell for every admin page.
 * Renders:  [ AdminSidebar | main content area ]
 *
 * Usage in routes:
 *   <Route element={<AdminLayout />}>
 *     <Route path="dashboard" element={<AdminDashboard />} />
 *     ...
 *   </Route>
 *
 * Children are rendered via <Outlet /> from react-router-dom.
 */
import { Outlet } from "react-router-dom";
import AdminSidebar from "./AdminSidebar";

const shellStyle = {
  display:        "flex",
  minHeight:      "100vh",
  background:     "#f8fafc",   // slate-50
  fontFamily:     "'Inter', 'Segoe UI', system-ui, sans-serif",
};

const mainStyle = {
  flex:           1,
  display:        "flex",
  flexDirection:  "column",
  minWidth:       0,           // prevents flex child overflow
  overflowY:      "auto",
};

export default function AdminLayout() {
  return (
    <div style={shellStyle}>
      <AdminSidebar />
      <main style={mainStyle}>
        <Outlet />
      </main>
    </div>
  );
}
