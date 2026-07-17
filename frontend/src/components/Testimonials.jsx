import { motion } from "framer-motion";
import { Star } from "lucide-react";

const TESTIMONIALS = [
  { name: "Dr. Priya Sharma",    role: "Cardiologist, Apollo Hospitals",
    text: "MediDeviceAI cut my device research time from hours to seconds. The PDF knowledge search is incredibly accurate — it pulls exact specifications from the original datasheet." },
  { name: "Rahul Mehta",         role: "Biomedical Engineer, Fortis Healthcare",
    text: "Finally a tool that understands biomedical queries. I asked about HeartStart FRx impedance specs and got the exact values from the service manual. Impressive." },
  { name: "Sister Agnes Paul",   role: "ICU Nurse Manager, AIIMS Delhi",
    text: "Our nursing staff uses it daily to look up ventilator settings and alarms. The voice input feature means no typing during rounds. Highly recommended." },
  { name: "Vikram Nair",         role: "Procurement Manager, Narayana Health",
    text: "The comparison feature saved us weeks during our ECG machine tender process. TC50 vs TC35 side-by-side with specs — exactly what procurement needed." },
  { name: "Dr. Meena Iyer",      role: "Neonatologist, Rainbow Children's Hospital",
    text: "Bubble CPAP queries, ventilator protocols, phototherapy thresholds — everything in one place. The AI understands neonatal clinical context remarkably well." },
  { name: "Arun Pillai",         role: "Hospital IT Director, Manipal Hospitals",
    text: "Deployment was seamless. The semantic cache keeps response times fast even under load, and the Supabase auth integration was enterprise-grade." },
];

function Stars() {
  return (
    <div style={{ display: "flex", gap: 3, marginBottom: 16 }}>
      {[...Array(5)].map((_, i) => (
        <Star key={i} size={16} fill="#f59e0b" color="#f59e0b" />
      ))}
    </div>
  );
}

export default function Testimonials() {
  return (
    <section className="ws-section" style={{ background: "#fff" }}>
      <div className="ws-container">
        <motion.div
          initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }} transition={{ duration: 0.5 }}
          style={{ textAlign: "center", marginBottom: 60 }}>
          <span className="ws-tag">Testimonials</span>
          <h2 className="ws-heading">Trusted by Healthcare Professionals</h2>
          <p className="ws-subheading" style={{ margin: "0 auto", textAlign: "center" }}>
            Clinicians, biomedical engineers, and procurement teams rely on
            MediDeviceAI every day across India's top hospitals.
          </p>
        </motion.div>

        <div className="ws-grid-3">
          {TESTIMONIALS.map((t, i) => (
            <motion.div key={t.name} className="ws-card"
              initial={{ opacity: 0, y: 28 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.08 }}
              style={{ padding: 36 }}>
              <Stars />
              <p style={{
                fontSize: "0.975rem", color: "#374151", lineHeight: 1.75,
                marginBottom: 24, fontStyle: "italic",
              }}>
                "{t.text}"
              </p>
              <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
                <div style={{
                  width: 46, height: 46, borderRadius: "50%",
                  background: "linear-gradient(135deg, #0ea5e9, #1e3a5f)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff", fontWeight: 800, fontSize: "1rem", flexShrink: 0,
                }}>
                  {t.name.charAt(0)}
                </div>
                <div>
                  <div style={{ fontWeight: 700, color: "#1e3a5f", fontSize: "0.975rem" }}>{t.name}</div>
                  <div style={{ fontSize: "0.85rem", color: "#64748b" }}>{t.role}</div>
                </div>
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
