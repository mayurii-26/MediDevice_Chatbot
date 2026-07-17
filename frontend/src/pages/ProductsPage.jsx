import { useState } from "react";
import { motion } from "framer-motion";
import "../website.css";
import { Heart, Activity, Wind, Baby, Stethoscope, Zap, Filter } from "lucide-react";

const ALL_PRODUCTS = [
  { icon: Activity,     color:"#0ea5e9", bg:"#e0f2fe", cat:"Cardiology",
    name:"PageWriter TC50",       desc:"12-lead ECG cardiograph, 10.4\" touchscreen, DXL algorithm, 200 ECG storage, wireless LAN." },
  { icon: Activity,     color:"#0ea5e9", bg:"#e0f2fe", cat:"Cardiology",
    name:"PageWriter TC10",       desc:"Portable, affordable ECG with colour display, Bluetooth, and Wi-Fi. Ideal for GP clinics." },
  { icon: Activity,     color:"#0ea5e9", bg:"#e0f2fe", cat:"Cardiology",
    name:"PageWriter TC35",       desc:"Mid-range 12-lead cardiograph with advanced filtering and HL7 connectivity." },
  { icon: Stethoscope,  color:"#10b981", bg:"#d1fae5", cat:"Cardiology",
    name:"ST80i Stress Test",     desc:"Integrated stress testing system with treadmill protocol support and real-time ST analysis." },
  { icon: Stethoscope,  color:"#10b981", bg:"#d1fae5", cat:"Cardiology",
    name:"Oscar 2 ABPM",          desc:"24-hour ambulatory blood pressure monitor with SphygmoCor technology." },
  { icon: Stethoscope,  color:"#10b981", bg:"#d1fae5", cat:"Cardiology",
    name:"Cardiac Workstation 7000", desc:"Clinical ECG management system for enterprise-wide ECG storage and review." },
  { icon: Zap,          color:"#f59e0b", bg:"#fef3c7", cat:"Defibrillation",
    name:"HeartStart FRx AED",    desc:"Rugged AED with SMART Analysis, CPR coaching, and pediatric capability." },
  { icon: Zap,          color:"#f59e0b", bg:"#fef3c7", cat:"Defibrillation",
    name:"HeartStart HS1",        desc:"Ultra-simple AED for lay responders. One button, clear voice guidance." },
  { icon: Heart,        color:"#ef4444", bg:"#fee2e2", cat:"Monitoring",
    name:"Efficia DFM100",        desc:"Compact defibrillator/monitor with pacing, SpO₂, EtCO₂, and NIBP." },
  { icon: Wind,         color:"#8b5cf6", bg:"#ede9fe", cat:"Respiratory",
    name:"Trilogy EV300",         desc:"Hospital ventilator for invasive and noninvasive positive-pressure ventilation." },
  { icon: Baby,         color:"#ec4899", bg:"#fce7f3", cat:"Neonatal",
    name:"Bubble CPAP System",    desc:"Gentle CPAP for premature infants with heated humidification." },
  { icon: Baby,         color:"#ec4899", bg:"#fce7f3", cat:"Neonatal",
    name:"Neonatal Ventilator",   desc:"Specialised neonatal ventilator with volume-targeted modes and leak compensation." },
];

const CATS = ["All", ...new Set(ALL_PRODUCTS.map(p => p.cat))];

export default function ProductsPage() {
  const [active, setActive] = useState("All");
  const filtered = active === "All" ? ALL_PRODUCTS : ALL_PRODUCTS.filter(p => p.cat === active);

  return (
    <main style={{ paddingTop: 68 }}>
      <section style={{ background: "linear-gradient(135deg,#f0f9ff,#e0f2fe)", padding: "60px 0 40px" }}>
        <div className="ws-container" style={{ textAlign: "center" }}>
          <span className="ws-tag">Product Catalog</span>
          <h1 className="ws-heading">Medical Device Portfolio</h1>
          <p className="ws-subheading" style={{ margin: "0 auto" }}>
            Browse our complete range of medical devices from leading manufacturers.
            Click any product to ask our AI for specifications, brochures, and more.
          </p>
        </div>
      </section>

      <section className="ws-section" style={{ background: "#f8fafc" }}>
        <div className="ws-container">
          {/* Filter bar */}
          <div style={{ display: "flex", alignItems: "center", gap: 10,
            flexWrap: "wrap", marginBottom: 36 }}>
            <Filter size={16} color="#64748b" />
            {CATS.map(cat => (
              <button key={cat} onClick={() => setActive(cat)}
                style={{
                  padding: "7px 16px", borderRadius: 20, border: "2px solid",
                  borderColor: active === cat ? "#0ea5e9" : "#e2e8f0",
                  background: active === cat ? "#e0f2fe" : "#fff",
                  color: active === cat ? "#0ea5e9" : "#64748b",
                  fontWeight: 700, fontSize: "0.82rem", cursor: "pointer",
                  transition: "all 0.15s",
                }}>
                {cat}
              </button>
            ))}
          </div>

          <div className="ws-grid-3">
            {filtered.map((p, i) => {
              const Icon = p.icon;
              return (
                <motion.div key={p.name} className="ws-card"
                  initial={{ opacity: 0, y: 20 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }}
                  transition={{ duration: 0.35, delay: i * 0.06 }}
                  style={{ padding: 28 }}>
                  <div style={{
                    width: 48, height: 48, borderRadius: 12, background: p.bg,
                    display: "flex", alignItems: "center", justifyContent: "center",
                    marginBottom: 16,
                  }}>
                    <Icon size={22} color={p.color} />
                  </div>
                  <div style={{ fontSize: "0.7rem", fontWeight: 700, color: p.color,
                    textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: 6 }}>
                    {p.cat}
                  </div>
                  <h3 style={{ fontWeight: 700, color: "#1e3a5f", marginBottom: 8, fontSize: "1rem" }}>
                    {p.name}
                  </h3>
                  <p style={{ fontSize: "0.875rem", color: "#64748b", lineHeight: 1.6 }}>
                    {p.desc}
                  </p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>
    </main>
  );
}
