import { motion } from "framer-motion";
import "../website.css";
import { Target, Eye, Award, Users } from "lucide-react";

const TEAM = [
  { name: "Dr. Arjun Kapoor",  role: "Chief Medical Officer",       initials: "AK" },
  { name: "Sunita Rao",        role: "Head of AI Engineering",       initials: "SR" },
  { name: "Vikram Desai",      role: "Biomedical Systems Lead",      initials: "VD" },
  { name: "Meena Krishnan",    role: "Clinical Informatics Director", initials: "MK" },
];

const VALUES = [
  { icon: Target, color: "#0ea5e9", title: "Accuracy First",
    desc: "Every answer is grounded in official documentation. We never guess." },
  { icon: Eye,    color: "#8b5cf6", title: "Clinical Transparency",
    desc: "Sources are always shown. Know exactly where every answer comes from." },
  { icon: Award,  color: "#10b981", title: "Regulatory Compliance",
    desc: "Built with FDA and CE regulatory standards in mind from day one." },
  { icon: Users,  color: "#f59e0b", title: "For Clinicians, By Clinicians",
    desc: "Designed with input from biomedical engineers and clinical staff." },
];

export default function About() {
  return (
    <main style={{ paddingTop: 68 }}>
      {/* Hero */}
      <section style={{
        background: "linear-gradient(135deg, #f0f9ff, #e0f2fe)",
        padding: "80px 0 60px",
      }}>
        <div className="ws-container" style={{ textAlign: "center" }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}>
            <span className="ws-tag">About Us</span>
            <h1 className="ws-heading" style={{ maxWidth: 640, margin: "0 auto 16px" }}>
              Building the Future of Medical Device Intelligence
            </h1>
            <p className="ws-subheading" style={{ margin: "0 auto", textAlign: "center" }}>
              MediDeviceAI was founded by a team of biomedical engineers and AI researchers
              with a mission to make critical device knowledge instantly accessible
              to every healthcare professional.
            </p>
          </motion.div>
        </div>
      </section>

      {/* Mission & Vision */}
      <section className="ws-section" style={{ background: "#fff" }}>
        <div className="ws-container">
          <div className="ws-grid-2" style={{ alignItems: "center", gap: 60 }}>
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.5 }}>
              <span className="ws-tag">Our Mission</span>
              <h2 className="ws-heading">Democratising Medical Device Knowledge</h2>
              <p style={{ color: "#64748b", lineHeight: 1.75, marginBottom: 16 }}>
                Healthcare professionals waste hours searching for device specifications,
                compatibility information, and clinical guidelines. We built MediDeviceAI
                to eliminate that friction.
              </p>
              <p style={{ color: "#64748b", lineHeight: 1.75 }}>
                By combining FAISS semantic search, PDF document intelligence, and Gemini AI,
                we deliver precise answers in seconds — not hours — regardless of how the
                question is phrased.
              </p>
            </motion.div>
            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.5 }}>
              <div style={{
                background: "linear-gradient(135deg, #1e3a5f, #0ea5e9)",
                borderRadius: 16, padding: 40, color: "#fff",
              }}>
                <Eye size={36} color="#bfdbfe" style={{ marginBottom: 20 }} />
                <h3 style={{ fontSize: "1.3rem", fontWeight: 800, marginBottom: 16 }}>Our Vision</h3>
                <p style={{ lineHeight: 1.7, color: "#bfdbfe", fontSize: "0.95rem" }}>
                  A world where every nurse, engineer, and physician has instant,
                  accurate access to the device knowledge they need — at the bedside,
                  in the OR, or in the procurement office.
                </p>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* Values */}
      <section className="ws-section" style={{ background: "#f8fafc" }}>
        <div className="ws-container">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }} style={{ textAlign: "center", marginBottom: 48 }}>
            <span className="ws-tag">Our Values</span>
            <h2 className="ws-heading">What We Stand For</h2>
          </motion.div>
          <div className="ws-grid-4">
            {VALUES.map((v, i) => {
              const Icon = v.icon;
              return (
                <motion.div key={v.title} className="ws-card"
                  initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                  style={{ padding: 28, textAlign: "center" }}>
                  <div style={{
                    width: 52, height: 52, borderRadius: 14, margin: "0 auto 16px",
                    background: v.color + "18",
                    display: "flex", alignItems: "center", justifyContent: "center",
                  }}>
                    <Icon size={24} color={v.color} />
                  </div>
                  <h3 style={{ fontWeight: 700, color: "#1e3a5f", marginBottom: 8 }}>{v.title}</h3>
                  <p style={{ fontSize: "0.875rem", color: "#64748b", lineHeight: 1.6 }}>{v.desc}</p>
                </motion.div>
              );
            })}
          </div>
        </div>
      </section>

      {/* Team */}
      <section className="ws-section" style={{ background: "#fff" }}>
        <div className="ws-container">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }} style={{ textAlign: "center", marginBottom: 48 }}>
            <span className="ws-tag">Our Team</span>
            <h2 className="ws-heading">The People Behind MediDeviceAI</h2>
          </motion.div>
          <div className="ws-grid-4">
            {TEAM.map((t, i) => (
              <motion.div key={t.name} className="ws-card"
                initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }} transition={{ delay: i * 0.1 }}
                style={{ padding: 28, textAlign: "center" }}>
                <div style={{
                  width: 64, height: 64, borderRadius: "50%", margin: "0 auto 16px",
                  background: "linear-gradient(135deg, #1e3a5f, #0ea5e9)",
                  display: "flex", alignItems: "center", justifyContent: "center",
                  color: "#fff", fontWeight: 800, fontSize: "1.2rem",
                }}>
                  {t.initials}
                </div>
                <h3 style={{ fontWeight: 700, color: "#1e3a5f", marginBottom: 4 }}>{t.name}</h3>
                <p style={{ fontSize: "0.82rem", color: "#64748b" }}>{t.role}</p>
              </motion.div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
