import { motion } from "framer-motion";
import "../website.css";
import ServicesSection from "../components/ServicesSection";
import { CheckCircle } from "lucide-react";

const PLANS = [
  { name: "Starter",    price: "Free",   color: "#64748b",
    features: ["50 AI queries/month", "Basic product search", "Document viewer", "Email support"] },
  { name: "Clinical",   price: "₹2,999", color: "#0ea5e9", highlight: true,
    features: ["Unlimited AI queries", "Full PDF knowledge base", "Voice input", "Priority support", "Export reports"] },
  { name: "Enterprise", price: "Custom", color: "#1e3a5f",
    features: ["Everything in Clinical", "Custom device catalog", "API access", "On-premise option", "Dedicated account manager"] },
];

export default function ServicesPage() {
  return (
    <main style={{ paddingTop: 68 }}>
      <section style={{ background: "linear-gradient(135deg,#f0f9ff,#e0f2fe)", padding: "60px 0 40px" }}>
        <div className="ws-container" style={{ textAlign: "center" }}>
          <span className="ws-tag">Services</span>
          <h1 className="ws-heading">Comprehensive Healthcare AI Services</h1>
          <p className="ws-subheading" style={{ margin: "0 auto" }}>
            From AI-powered query resolution to enterprise document management,
            we offer the complete suite of medical device intelligence services.
          </p>
        </div>
      </section>

      <ServicesSection />

      {/* Pricing */}
      <section className="ws-section" style={{ background: "#f8fafc" }}>
        <div className="ws-container">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }} style={{ textAlign: "center", marginBottom: 48 }}>
            <span className="ws-tag">Pricing</span>
            <h2 className="ws-heading">Simple, Transparent Pricing</h2>
          </motion.div>
          <div className="ws-grid-3">
            {PLANS.map((plan, i) => (
              <motion.div key={plan.name} className="ws-card"
                initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                style={{
                  padding: 32, textAlign: "center",
                  border: plan.highlight ? `2px solid #0ea5e9` : "1px solid #e2e8f0",
                  position: "relative",
                }}>
                {plan.highlight && (
                  <div style={{
                    position: "absolute", top: -12, left: "50%", transform: "translateX(-50%)",
                    background: "#0ea5e9", color: "#fff", fontSize: "0.72rem",
                    fontWeight: 700, padding: "3px 14px", borderRadius: 20,
                  }}>Most Popular</div>
                )}
                <div style={{ fontWeight: 700, color: plan.color,
                  fontSize: "0.85rem", textTransform: "uppercase",
                  letterSpacing: "0.5px", marginBottom: 12 }}>
                  {plan.name}
                </div>
                <div style={{ fontSize: "2.4rem", fontWeight: 900, color: "#1e3a5f",
                  marginBottom: 24 }}>
                  {plan.price}
                  {plan.price !== "Free" && plan.price !== "Custom" && (
                    <span style={{ fontSize: "0.9rem", color: "#64748b", fontWeight: 400 }}>/mo</span>
                  )}
                </div>
                <ul style={{ listStyle: "none", padding: 0, margin: "0 0 28px",
                  display: "flex", flexDirection: "column", gap: 10 }}>
                  {plan.features.map(f => (
                    <li key={f} style={{ display: "flex", alignItems: "center",
                      gap: 8, fontSize: "0.875rem", color: "#374151" }}>
                      <CheckCircle size={15} color="#10b981" />
                      {f}
                    </li>
                  ))}
                </ul>
                <button style={{
                  width: "100%", padding: "11px", borderRadius: 8,
                  background: plan.highlight ? "#0ea5e9" : "transparent",
                  color: plan.highlight ? "#fff" : "#1e3a5f",
                  border: plan.highlight ? "none" : "2px solid #1e3a5f",
                  fontWeight: 700, cursor: "pointer", fontSize: "0.9rem",
                }}>
                  {plan.price === "Custom" ? "Contact Us" : "Get Started"}
                </button>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
