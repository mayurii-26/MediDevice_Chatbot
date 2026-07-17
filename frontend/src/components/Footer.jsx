import { Link } from "react-router-dom";
import { Activity, Mail, Phone, MapPin } from "lucide-react";

const LINKS = {
  Product: [
    { label: "Medical Devices",  to: "/products" },
    { label: "AI Assistant",     to: "/" },
    { label: "Document Library", to: "/resources" },
    { label: "Resources",        to: "/resources" },
  ],
  Company: [
    { label: "About Us",  to: "/about" },
    { label: "Services",  to: "/services" },
    { label: "Contact",   to: "/contact" },
    { label: "Careers",   to: "/about" },
  ],
  Legal: [
    { label: "Privacy Policy",   to: "/" },
    { label: "Terms of Service", to: "/" },
    { label: "Cookie Policy",    to: "/" },
  ],
};

const CONTACT = [
  { icon: Mail,   text: "support@medideviceai.com" },
  { icon: Phone,  text: "+91 98765 43210" },
  { icon: MapPin, text: "BKC, Mumbai, Maharashtra, India" },
];

export default function Footer() {
  return (
    <footer style={{ background: "#0c2340", color: "#cbd5e1", paddingTop: 72 }}>
      <div className="ws-container">
        <div style={{
          display: "grid",
          gridTemplateColumns: "2fr 1fr 1fr 1fr",
          gap: 48, paddingBottom: 56,
        }} className="footer-grid">

          {/* Brand */}
          <div>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
              <div style={{ background: "#0ea5e9", borderRadius: 10, padding: 8, display: "flex" }}>
                <Activity size={22} color="#fff" />
              </div>
              <span style={{ fontWeight: 900, fontSize: "1.3rem", color: "#fff" }}>
                MediDevice<span style={{ color: "#0ea5e9" }}>AI</span>
              </span>
            </div>
            <p style={{ fontSize: "0.975rem", lineHeight: 1.75, maxWidth: 300, marginBottom: 28, color: "#94a3b8" }}>
              AI-powered medical device intelligence platform. Instant answers,
              accurate documentation, and clinical support — available 24/7.
            </p>
            <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
              {CONTACT.map(({ icon: Icon, text }) => (
                <div key={text} style={{ display: "flex", alignItems: "center", gap: 10,
                  fontSize: "0.9rem", color: "#94a3b8" }}>
                  <Icon size={15} color="#0ea5e9" />
                  {text}
                </div>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {Object.entries(LINKS).map(([heading, items]) => (
            <div key={heading}>
              <div style={{ fontWeight: 800, color: "#fff", marginBottom: 20,
                fontSize: "0.9rem", textTransform: "uppercase", letterSpacing: "0.6px" }}>
                {heading}
              </div>
              <ul style={{ listStyle: "none", margin: 0, padding: 0,
                display: "flex", flexDirection: "column", gap: 12 }}>
                {items.map(({ label, to }) => (
                  <li key={label}>
                    <Link to={to} style={{
                      color: "#94a3b8", textDecoration: "none",
                      fontSize: "0.95rem", transition: "color 0.15s",
                    }}
                    onMouseEnter={e => e.target.style.color = "#0ea5e9"}
                    onMouseLeave={e => e.target.style.color = "#94a3b8"}>
                      {label}
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        {/* Bottom bar */}
        <div style={{
          borderTop: "1px solid #1e3a5f", padding: "24px 0",
          display: "flex", justifyContent: "space-between",
          alignItems: "center", flexWrap: "wrap", gap: 12,
        }}>
          <span style={{ fontSize: "0.9rem", color: "#64748b" }}>
            © {new Date().getFullYear()} MediDeviceAI. All rights reserved.
          </span>
          <span style={{ fontSize: "0.9rem", color: "#64748b" }}>
            AI Medical Knowledge Platform · Powered by Gemini AI · FAISS
          </span>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .footer-grid { grid-template-columns: 1fr 1fr !important; }
        }
        @media (max-width: 480px) {
          .footer-grid { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </footer>
  );
}
