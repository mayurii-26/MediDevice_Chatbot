import { useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import "../website.css";
import { Mail, Phone, MapPin, Send } from "lucide-react";

const API = "http://127.0.0.1:8000";

export default function ContactPage() {
  const [form, setForm]     = useState({ name: "", email: "", message: "" });
  const [status, setStatus] = useState(null); // "ok" | "err" | null
  const [sending, setSending] = useState(false);

  const handleChange = e => setForm(f => ({ ...f, [e.target.name]: e.target.value }));

  const handleSubmit = async e => {
    e.preventDefault();
    setSending(true); setStatus(null);
    try {
      await axios.post(`${API}/contact`, form);
      setStatus("ok");
      setForm({ name: "", email: "", message: "" });
    } catch {
      setStatus("err");
    } finally { setSending(false); }
  };

  return (
    <main style={{ paddingTop: 68 }}>
      <section style={{ background: "linear-gradient(135deg,#f0f9ff,#e0f2fe)", padding: "60px 0 40px" }}>
        <div className="ws-container" style={{ textAlign: "center" }}>
          <span className="ws-tag">Contact</span>
          <h1 className="ws-heading">Get in Touch</h1>
          <p className="ws-subheading" style={{ margin: "0 auto" }}>
            Have a question about our platform, a specific device, or enterprise pricing?
            Our team responds within one business day.
          </p>
        </div>
      </section>

      <section className="ws-section" style={{ background: "#fff" }}>
        <div className="ws-container">
          <div className="ws-grid-2" style={{ gap: 60, alignItems: "flex-start" }}>

            {/* Info */}
            <motion.div initial={{ opacity: 0, x: -20 }} whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.5 }}>
              <h2 style={{ fontSize: "1.5rem", fontWeight: 800, color: "#1e3a5f", marginBottom: 24 }}>
                Contact Information
              </h2>
              {[
                { icon: Mail,    label: "Email",   value: "support@medideviceai.com" },
                { icon: Phone,   label: "Phone",   value: "+91 98765 43210" },
                { icon: MapPin,  label: "Address", value: "BKC, Mumbai, Maharashtra 400051, India" },
              ].map(({ icon: Icon, label, value }) => (
                <div key={label} style={{ display: "flex", gap: 16, marginBottom: 28 }}>
                  <div style={{
                    width: 44, height: 44, borderRadius: 10, background: "#e0f2fe",
                    display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
                  }}>
                    <Icon size={20} color="#0ea5e9" />
                  </div>
                  <div>
                    <div style={{ fontSize: "0.78rem", color: "#94a3b8",
                      fontWeight: 700, textTransform: "uppercase",
                      letterSpacing: "0.4px", marginBottom: 3 }}>
                      {label}
                    </div>
                    <div style={{ color: "#1e3a5f", fontWeight: 600 }}>{value}</div>
                  </div>
                </div>
              ))}

              <div style={{
                background: "linear-gradient(135deg,#1e3a5f,#0ea5e9)",
                borderRadius: 14, padding: 28, color: "#fff", marginTop: 12,
              }}>
                <h3 style={{ fontWeight: 800, marginBottom: 10 }}>Business Hours</h3>
                <p style={{ fontSize: "0.875rem", color: "#bfdbfe", lineHeight: 1.7 }}>
                  Monday – Friday: 9:00 AM – 6:00 PM IST<br />
                  Saturday: 10:00 AM – 2:00 PM IST<br />
                  AI Assistant: Available 24/7
                </p>
              </div>
            </motion.div>

            {/* Form */}
            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true }} transition={{ duration: 0.5 }}>
              <div className="ws-card" style={{ padding: 36 }}>
                <h2 style={{ fontSize: "1.3rem", fontWeight: 800, color: "#1e3a5f", marginBottom: 24 }}>
                  Send a Message
                </h2>
                <form onSubmit={handleSubmit}>
                  {[
                    { name: "name",    label: "Your Name",    type: "text",  placeholder: "Dr. Ananya Sharma" },
                    { name: "email",   label: "Email Address", type: "email", placeholder: "ananya@hospital.com" },
                  ].map(f => (
                    <div key={f.name} style={{ marginBottom: 16 }}>
                      <label style={{ display: "block", fontWeight: 600, color: "#374151",
                        fontSize: "0.85rem", marginBottom: 6 }}>{f.label}</label>
                      <input
                        name={f.name} type={f.type} required
                        value={form[f.name]} onChange={handleChange}
                        placeholder={f.placeholder}
                        style={{
                          width: "100%", padding: "11px 14px", borderRadius: 8,
                          border: "1.5px solid #e2e8f0", fontSize: "0.9rem",
                          fontFamily: "inherit", background: "#f8fafc",
                          color: "#1a1a2e", outline: "none", boxSizing: "border-box",
                        }}
                      />
                    </div>
                  ))}
                  <div style={{ marginBottom: 20 }}>
                    <label style={{ display: "block", fontWeight: 600, color: "#374151",
                      fontSize: "0.85rem", marginBottom: 6 }}>Message</label>
                    <textarea
                      name="message" required rows={5}
                      value={form.message} onChange={handleChange}
                      placeholder="Tell us about your device query, integration need, or enterprise requirements..."
                      style={{
                        width: "100%", padding: "11px 14px", borderRadius: 8,
                        border: "1.5px solid #e2e8f0", fontSize: "0.9rem",
                        fontFamily: "inherit", resize: "vertical", background: "#f8fafc",
                        color: "#1a1a2e", outline: "none", boxSizing: "border-box",
                      }}
                    />
                  </div>

                  {status === "ok" && (
                    <div style={{ background: "#f0fdf4", color: "#15803d", padding: "10px 14px",
                      borderRadius: 8, fontSize: "0.875rem", fontWeight: 600, marginBottom: 14 }}>
                      ✓ Message sent successfully! We'll respond within 24 hours.
                    </div>
                  )}
                  {status === "err" && (
                    <div style={{ background: "#fef2f2", color: "#dc2626", padding: "10px 14px",
                      borderRadius: 8, fontSize: "0.875rem", fontWeight: 600, marginBottom: 14 }}>
                      Failed to send. Please try again or email us directly.
                    </div>
                  )}

                  <button type="submit" disabled={sending} className="ws-btn-primary"
                    style={{ width: "100%", justifyContent: "center",
                      opacity: sending ? 0.7 : 1 }}>
                    <Send size={16} />
                    {sending ? "Sending…" : "Send Message"}
                  </button>
                </form>
              </div>
            </motion.div>

          </div>
        </div>
      </section>
    </main>
  );
}
