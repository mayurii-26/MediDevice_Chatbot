import { motion } from "framer-motion";
import { Brain, Search, FileText, Clock, ShieldCheck, HeadphonesIcon } from "lucide-react";

const REASONS = [
  { icon: Brain,           color: "#0ea5e9",
    title: "Gemini AI Engine",
    desc: "Powered by Google Gemini 2.0 Flash for precise, context-aware answers about every device." },
  { icon: Search,          color: "#8b5cf6",
    title: "Semantic FAISS Search",
    desc: "Vector-based retrieval finds the closest product match even for vague or abbreviated queries." },
  { icon: FileText,        color: "#10b981",
    title: "PDF Knowledge Base",
    desc: "Full brochures and datasheets are indexed and searchable — not just marketing summaries." },
  { icon: Clock,           color: "#f59e0b",
    title: "Instant Responses",
    desc: "Semantic cache returns repeated questions in milliseconds. No waiting, no API overhead." },
  { icon: ShieldCheck,     color: "#ef4444",
    title: "Clinically Accurate",
    desc: "Answers are grounded in official product documentation. No hallucinated specifications." },
  { icon: HeadphonesIcon,  color: "#ec4899",
    title: "24/7 Availability",
    desc: "AI assistant available around the clock for procurement, clinical, and technical queries." },
];

export default function WhyChooseUs() {
  return (
    <section className="ws-section" style={{ background: "#fff" }}>
      <div className="ws-container">
        <motion.div
          initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ duration: 0.5 }}
          style={{ textAlign: "center", marginBottom: 60 }}>
          <span className="ws-tag">Why MediDeviceAI</span>
          <h2 className="ws-heading">The Smarter Way to<br />Manage Medical Device Knowledge</h2>
          <p className="ws-subheading" style={{ margin: "0 auto", textAlign: "center" }}>
            Built for biomedical engineers, procurement teams, and clinical staff
            who need accurate device information fast.
          </p>
        </motion.div>

        <div className="ws-grid-3">
          {REASONS.map((r, i) => {
            const Icon = r.icon;
            return (
              <motion.div key={r.title}
                initial={{ opacity: 0, y: 20 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.07 }}
                style={{ padding: "28px 24px", display: "flex", gap: 20 }}>
                <div style={{
                  flexShrink: 0, width: 50, height: 50, borderRadius: 12,
                  background: r.color + "18",
                  display: "flex", alignItems: "center", justifyContent: "center",
                }}>
                  <Icon size={24} color={r.color} />
                </div>
                <div>
                  <h3 style={{ fontSize: "1.1rem", fontWeight: 800, color: "#1e3a5f", marginBottom: 8 }}>
                    {r.title}
                  </h3>
                  <p style={{ fontSize: "0.975rem", color: "#64748b", lineHeight: 1.65 }}>
                    {r.desc}
                  </p>
                </div>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
