import { motion } from "framer-motion";
import { Bot, BookOpen, Wrench, BarChart2, ShoppingCart, GraduationCap } from "lucide-react";

const SERVICES = [
  { icon: Bot,           color: "#0ea5e9", bg: "#e0f2fe",
    title: "AI Clinical Assistant",
    desc: "Ask any question about medical devices. Get instant, accurate answers sourced from official documentation and clinical guidelines." },
  { icon: BookOpen,      color: "#8b5cf6", bg: "#ede9fe",
    title: "Document Library",
    desc: "Searchable repository of brochures, datasheets, user manuals, and service guides for all supported devices." },
  { icon: Wrench,        color: "#10b981", bg: "#d1fae5",
    title: "Technical Support",
    desc: "Biomedical and BMET-level specifications, safety alerts, and maintenance documentation at your fingertips." },
  { icon: BarChart2,     color: "#f59e0b", bg: "#fef3c7",
    title: "Procurement Intelligence",
    desc: "Compare device specifications, features, and pricing across categories to support informed purchasing decisions." },
  { icon: ShoppingCart,  color: "#ef4444", bg: "#fee2e2",
    title: "Product Sourcing",
    desc: "Identify authorised distributors, check availability, and access product ordering documentation quickly." },
  { icon: GraduationCap, color: "#ec4899", bg: "#fce7f3",
    title: "Clinical Training",
    desc: "On-demand device operation guides, quick-start cards, and training materials for clinical and biomedical staff." },
];

export default function ServicesSection() {
  return (
    <section className="ws-section" style={{ background: "#f8fafc" }}>
      <div className="ws-container">
        <motion.div
          initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ duration: 0.5 }}
          style={{ textAlign: "center", marginBottom: 60 }}>
          <span className="ws-tag">Our Services</span>
          <h2 className="ws-heading">Everything You Need in One Platform</h2>
          <p className="ws-subheading" style={{ margin: "0 auto", textAlign: "center" }}>
            From AI-powered Q&amp;A to procurement support, MediDeviceAI covers
            the full device knowledge lifecycle.
          </p>
        </motion.div>

        <div className="ws-grid-3">
          {SERVICES.map((s, i) => {
            const Icon = s.icon;
            return (
              <motion.div key={s.title} className="ws-card"
                initial={{ opacity: 0, y: 24 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.08 }}
                style={{ padding: 36 }}>
                <div style={{
                  width: 58, height: 58, borderRadius: 14, background: s.bg,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  marginBottom: 22,
                }}>
                  <Icon size={28} color={s.color} />
                </div>
                <h3 style={{ fontSize: "1.15rem", fontWeight: 800, color: "#1e3a5f", marginBottom: 10 }}>
                  {s.title}
                </h3>
                <p style={{ fontSize: "0.975rem", color: "#64748b", lineHeight: 1.65 }}>
                  {s.desc}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
