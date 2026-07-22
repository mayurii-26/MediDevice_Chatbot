/**
 * AdminSidebar.jsx
 *
 * Left navigation sidebar for the admin portal.
 * Uses lucide-react icons and inline styles — consistent with project conventions.
 * Highlights the active route via react-router-dom NavLink.
 */
import { NavLink, useNavigate } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  BarChart2,
  Package,
  FileText,
  Download,
  MessageSquare,
  HelpCircle,
  MessagesSquare,
  BrainCircuit,
  Activity,
  Settings,
  LogOut,
  Stethoscope,
} from "lucide-react";
import { useAdminAuth } from "../context/AdminAuthContext";

// ── Nav items ──────────────────────────────────────────────────────────────
const NAV_ITEMS = [
  { label: "Dashboard",        to: "/admin/dashboard",         icon: LayoutDashboard },
  { label: "Users",            to: "/admin/users",             icon: Users           },
  { label: "Query Analytics",  to: "/admin/query-analytics",   icon: BarChart2       },
  { label: "Products",         to: "/admin/products",          icon: Package         },
  { label: "Documents",        to: "/admin/documents",         icon: FileText        },
  { label: "Downloads",        to: "/admin/downloads",         icon: Download        },
  { label: "Contact Requests", to: "/admin/contact-requests",  icon: MessageSquare   },
  { label: "Unknown Queries",  to: "/admin/unknown-queries",   icon: HelpCircle      },
  { label: "Conversations",    to: "/admin/conversations",     icon: MessagesSquare  },
  { label: "AI Analytics",     to: "/admin/ai-analytics",      icon: BrainCircuit    },
  { label: "System Health",    to: "/admin/system-health",     icon: Activity        },
  { label: "Settings",         to: "/admin/settings",          icon: Settings        },
];

// ── Styles ─────────────────────────────────────────────────────────────────
const SIDEBAR_WIDTH = 240;

const sidebarStyle = {
  width:           SIDEBAR_WIDTH,
  minHeight:       "100vh",
  background:      "#0f172a",          // slate-900
  display:         "flex",
  flexDirection:   "column",
  flexShrink:      0,
  borderRight:     "1px solid #1e293b",
};

const brandStyle = {
  padding:         "24px 20px 20px",
  borderBottom:    "1px solid #1e293b",
  display:         "flex",
  alignItems:      "center",
  gap:             10,
};

const brandIconStyle = {
  background:      "#0ea5e9",
  borderRadius:    8,
  padding:         7,
  display:         "flex",
  alignItems:      "center",
  justifyContent:  "center",
};

const brandTextStyle = {
  fontWeight:  800,
  fontSize:    "1rem",
  color:       "#f1f5f9",
  letterSpacing: "-0.3px",
};

const brandSubStyle = {
  fontSize:    "0.65rem",
  color:       "#64748b",
  fontWeight:  600,
  letterSpacing: "0.08em",
  textTransform: "uppercase",
  marginTop:   1,
};

const navStyle = {
  flex:        1,
  overflowY:   "auto",
  padding:     "12px 10px",
};

const footerStyle = {
  padding:     "12px 10px 20px",
  borderTop:   "1px solid #1e293b",
};

function navLinkStyle({ isActive }) {
  return {
    display:        "flex",
    alignItems:     "center",
    gap:            10,
    padding:        "9px 12px",
    borderRadius:   8,
    marginBottom:   2,
    textDecoration: "none",
    fontSize:       "0.875rem",
    fontWeight:     isActive ? 600 : 400,
    color:          isActive ? "#f1f5f9"  : "#94a3b8",
    background:     isActive ? "#1e293b" : "transparent",
    transition:     "background 0.15s, color 0.15s",
  };
}

const logoutBtnStyle = {
  display:        "flex",
  alignItems:     "center",
  gap:            10,
  padding:        "9px 12px",
  borderRadius:   8,
  width:          "100%",
  border:         "none",
  background:     "transparent",
  color:          "#ef4444",
  fontSize:       "0.875rem",
  fontWeight:     500,
  cursor:         "pointer",
  textAlign:      "left",
  transition:     "background 0.15s",
};

// ── Component ──────────────────────────────────────────────────────────────
export default function AdminSidebar() {
  const { adminLogout } = useAdminAuth();
  const navigate        = useNavigate();

  function handleLogout() {
    adminLogout();
    navigate("/admin/login", { replace: true });
  }

  return (
    <nav style={sidebarStyle} aria-label="Admin navigation">
      {/* Brand */}
      <div style={brandStyle}>
        <div style={brandIconStyle}>
          <Stethoscope size={18} color="#fff" />
        </div>
        <div>
          <div style={brandTextStyle}>
            MediDevice<span style={{ color: "#0ea5e9" }}>AI</span>
          </div>
          <div style={brandSubStyle}>Admin Portal</div>
        </div>
      </div>

      {/* Navigation items */}
      <div style={navStyle}>
        {NAV_ITEMS.map(({ label, to, icon: Icon }) => (
          <NavLink key={to} to={to} style={navLinkStyle}>
            <Icon size={16} />
            {label}
          </NavLink>
        ))}
      </div>

      {/* Logout */}
      <div style={footerStyle}>
        <button
          style={logoutBtnStyle}
          onClick={handleLogout}
          onMouseEnter={e => { e.currentTarget.style.background = "#1e293b"; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; }}
        >
          <LogOut size={16} />
          Logout
        </button>
      </div>
    </nav>
  );
}
