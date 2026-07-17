import { useState, forwardRef } from "react";
import axios from "axios";

const ContactForm = forwardRef(function ContactForm(props, ref) {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState(null); // "success" | "error"
  const [submitting, setSubmitting] = useState(false);

  const submitForm = async () => {
    if (!name.trim() || !email.trim() || !message.trim()) {
      setStatus("fill");
      return;
    }

    setSubmitting(true);
    setStatus(null);

    try {
      await axios.post("http://127.0.0.1:8000/contact", {
        name,
        email,
        message,
      });

      setStatus("success");
      setName("");
      setEmail("");
      setMessage("");
    } catch {
      setStatus("error");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="contact-form" ref={ref}>
      <h3>📬 Contact Support</h3>

      <input
        type="text"
        placeholder="Your Name"
        value={name}
        onChange={(e) => setName(e.target.value)}
      />

      <input
        type="email"
        placeholder="Your Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
      />

      <textarea
        rows="4"
        placeholder="Describe your issue or question..."
        value={message}
        onChange={(e) => setMessage(e.target.value)}
      />

      <button
        className="ask-btn"
        onClick={submitForm}
        disabled={submitting}
      >
        {submitting ? "Sending..." : "Submit Query"}
      </button>

      {status === "success" && (
        <p className="contact-status success">
          ✅ Query submitted successfully. We will get back to you shortly.
        </p>
      )}
      {status === "error" && (
        <p className="contact-status error">
          ❌ Failed to send. Please try again or email support@medidevicechatbot.com
        </p>
      )}
      {status === "fill" && (
        <p className="contact-status error">
          ⚠️ Please fill in all fields before submitting.
        </p>
      )}
    </div>
  );
});

export default ContactForm;
