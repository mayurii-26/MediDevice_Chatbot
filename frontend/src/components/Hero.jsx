import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { ArrowRight, MessageCircle, ShieldCheck, Cpu, BarChart3 } from "lucide-react";

const BADGES = [
  { icon: ShieldCheck, label: "FDA Compliant" },
  { icon: Cpu,         label: "AI-Powered" },
  { icon: BarChart3,   label: "Real-Time Analytics" },
];

const fadeUp = (delay = 0) => ({
  initial: { opacity: 0, y: 32 },
  animate: { opacity: 1, y: 0 },
  transition: { duration: 0.6, delay, ease: "easeOut" },
});

export default function Hero({ onOpenChat }) {
  return (
    <section style={{
      minHeight: "100vh",
      background: "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 55%, #f8fafc 100%)",
      display: "flex", alignItems: "center",
      paddingTop: 76, overflow: "hidden", position: "relative",
    }}>
      <div style={{
        position: "absolute", top: -140, right: -140, width: 640, height: 640,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(14,165,233,0.12) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", bottom: -100, left: -100, width: 440, height: 440,
        borderRadius: "50%",
        background: "radial-gradient(circle, rgba(30,58,95,0.07) 0%, transparent 70%)",
        pointerEvents: "none",
      }} />

      <div className="ws-container" style={{ position: "relative", zIndex: 1, width: "100%" }}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 72, alignItems: "center" }}
          className="hero-grid">

          {/* Left */}
          <div>
            <motion.div {...fadeUp(0)}>
              <span className="ws-tag">🏥 Enterprise Healthcare AI</span>
            </motion.div>

            <motion.h1 {...fadeUp(0.1)} style={{
              fontSize: "clamp(2.8rem, 5vw, 4rem)",
              fontWeight: 900, color: "#1e3a5f",
              lineHeight: 1.1, marginBottom: 24, letterSpacing: "-1px",
            }}>
              AI-Powered<br />
              <span style={{ color: "#0ea5e9" }}>Medical Device</span><br />
              Intelligence
            </motion.h1>

            <motion.p {...fadeUp(0.2)} style={{
              fontSize: "1.2rem", color: "#64748b", lineHeight: 1.75,
              marginBottom: 36, maxWidth: 500,
            }}>
              Instantly access specifications, brochures, and clinical data for
              medical devices from leading manufacturers. Powered by FAISS semantic search and
              Gemini AI — answers in seconds, not hours.
            </motion.p>

            <motion.div {...fadeUp(0.3)} style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
              <Link to="/products" className="ws-btn-primary">
                Explore Products <ArrowRight size={18} />
              </Link>
              <button className="ws-btn-outline" onClick={onOpenChat}>
                <MessageCircle size={18} /> Chat with AI
              </button>
            </motion.div>

            <motion.div {...fadeUp(0.4)} style={{ display: "flex", gap: 28, marginTop: 44, flexWrap: "wrap" }}>
              {BADGES.map(({ icon: Icon, label }) => (
                <div key={label} style={{
                  display: "flex", alignItems: "center", gap: 8,
                  color: "#1e3a5f", fontSize: "0.95rem", fontWeight: 600,
                }}>
                  <Icon size={17} color="#0ea5e9" /> {label}
                </div>
              ))}
            </motion.div>
          </div>

          {/* Right — mock chat */}
          <motion.div initial={{ opacity: 0, x: 48 }} animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.7, delay: 0.2 }} className="hero-visual">
            <div style={{
              background: "#fff", borderRadius: 24,
              boxShadow: "0 20px 72px rgba(30,58,95,0.15)",
              padding: 36, border: "1px solid #e0f2fe",
            }}>
              <div style={{ marginBottom: 24, display: "flex", alignItems: "center", gap: 12 }}>
                <div style={{ background: "#e0f2fe", borderRadius: 10, padding: 10 }}>
                  <MessageCircle size={22} color="#0ea5e9" />
                </div>
                <div>
                  <div style={{ fontWeight: 800, color: "#1e3a5f", fontSize: "1.05rem" }}>
                    MediDevice AI Assistant
                  </div>
                  <div style={{ fontSize: "0.8rem", color: "#22c55e", fontWeight: 600 }}>● Online</div>
                </div>
              </div>

              {[
                { from: "user", text: "What are the specs of PageWriter TC50?" },
                { from: "bot",  text: "The PageWriter TC50 is a 12-lead ECG cardiograph with a 10.4\" touchscreen, DXL algorithm, wireless connectivity, and 200 ECG internal storage." },
                { from: "user", text: "Compare TC50 vs TC10" },
              ].map((m, i) => (
                <motion.div key={i}
                  initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: 0.5 + i * 0.18 }}
                  style={{ marginBottom: 12, display: "flex",
                    justifyContent: m.from === "user" ? "flex-end" : "flex-start" }}>
                  <div style={{
                    maxWidth: "80%", padding: "12px 16px", borderRadius: 14,
                    fontSize: "0.9rem", lineHeight: 1.55,
                    background: m.from === "user" ? "#0ea5e9" : "#f0f9ff",
                    color: m.from === "user" ? "#fff" : "#1e3a5f",
                    borderBottomRightRadius: m.from === "user" ? 2 : 14,
                    borderBottomLeftRadius:  m.from === "bot"  ? 2 : 14,
                  }}>{m.text}</div>
                </motion.div>
              ))}

              <motion.div animate={{ opacity: [1, 0.35, 1] }}
                transition={{ repeat: Infinity, duration: 1.5 }}
                style={{ fontSize: "0.85rem", color: "#94a3b8", paddingLeft: 4, marginTop: 4 }}>
                AI is thinking…
              </motion.div>
            </div>
          </motion.div>
        </div>
      </div>

      <style>{`
        @media (max-width: 900px) {
          .hero-grid { grid-template-columns: 1fr !important; gap: 36px !important; }
          .hero-visual { display: none; }
        }
      `}</style>
    </section>
  );
}
