import { motion } from "framer-motion";
import { Heart, Activity, Wind, Baby, Stethoscope, Zap } from "lucide-react";

const PRODUCTS = [
  { icon: Activity,    color: "#0ea5e9", bg: "#e0f2fe", category: "Cardiology",
    name: "PageWriter TC50",
    desc: "12-lead ECG cardiograph with 10.4\" touchscreen, DXL algorithm, and wireless connectivity." },
  { icon: Zap,         color: "#f59e0b", bg: "#fef3c7", category: "Defibrillation",
    name: "HeartStart FRx AED",
    desc: "Rugged, portable AED with SMART Analysis technology for fast, accurate shock delivery." },
  { icon: Heart,       color: "#ef4444", bg: "#fee2e2", category: "Monitoring",
    name: "Efficia DFM100",
    desc: "Compact defibrillator/monitor with pacing, SpO₂, and capnography in a lightweight design." },
  { icon: Wind,        color: "#8b5cf6", bg: "#ede9fe", category: "Respiratory",
    name: "Trilogy EV300",
    desc: "Hospital ventilator supporting invasive and noninvasive ventilation with advanced monitoring." },
  { icon: Baby,        color: "#ec4899", bg: "#fce7f3", category: "Neonatal",
    name: "Bubble CPAP System",
    desc: "Gentle, effective respiratory support for premature infants with continuous positive airway pressure." },
  { icon: Stethoscope, color: "#10b981", bg: "#d1fae5", category: "Stress Testing",
    name: "ST80i System",
    desc: "Integrated stress testing with treadmill, ECG acquisition, and clinical reporting software." },
];

export default function FeaturedProducts() {
  return (
    <section className="ws-section" style={{ background: "#f8fafc" }}>
      <div className="ws-container">
        <motion.div
          initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ duration: 0.5 }}
          style={{ textAlign: "center", marginBottom: 60 }}>
          <span className="ws-tag">Product Catalog</span>
          <h2 className="ws-heading" style={{ margin: "0 auto 16px" }}>Featured Medical Devices</h2>
          <p className="ws-subheading" style={{ margin: "0 auto", textAlign: "center" }}>
            Explore our range of medical devices from leading manufacturers, each backed by
            full AI-powered documentation and support.
          </p>
        </motion.div>

        <div className="ws-grid-3">
          {PRODUCTS.map((p, i) => {
            const Icon = p.icon;
            return (
              <motion.div key={p.name} className="ws-card"
                initial={{ opacity: 0, y: 28 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.45, delay: i * 0.08 }}
                style={{ padding: 36 }}>
                <div style={{
                  width: 58, height: 58, borderRadius: 14,
                  background: p.bg, display: "flex", alignItems: "center",
                  justifyContent: "center", marginBottom: 22,
                }}>
                  <Icon size={28} color={p.color} />
                </div>
                <div style={{
                  fontSize: "0.75rem", fontWeight: 800, color: p.color,
                  textTransform: "uppercase", letterSpacing: "0.6px", marginBottom: 8,
                }}>
                  {p.category}
                </div>
                <h3 style={{ fontSize: "1.2rem", fontWeight: 800, color: "#1e3a5f", marginBottom: 12 }}>
                  {p.name}
                </h3>
                <p style={{ fontSize: "0.975rem", color: "#64748b", lineHeight: 1.65 }}>
                  {p.desc}
                </p>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
