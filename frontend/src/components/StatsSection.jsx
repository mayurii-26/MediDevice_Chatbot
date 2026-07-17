import { useEffect, useRef, useState } from "react";
import { motion } from "framer-motion";

const STATS = [
  { value: 500,  suffix: "+",  label: "Medical Devices Covered" },
  { value: 99,   suffix: "%",  label: "Query Accuracy Rate" },
  { value: 50,   suffix: "K+", label: "Questions Answered" },
  { value: 24,   suffix: "/7", label: "AI Availability" },
];

function CountUp({ target, suffix }) {
  const [count, setCount] = useState(0);
  const ref = useRef(null);
  const started = useRef(false);

  useEffect(() => {
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting && !started.current) {
        started.current = true;
        const steps = 60;
        const increment = target / steps;
        let current = 0;
        const timer = setInterval(() => {
          current += increment;
          if (current >= target) { setCount(target); clearInterval(timer); }
          else setCount(Math.floor(current));
        }, 1800 / steps);
      }
    }, { threshold: 0.4 });
    if (ref.current) observer.observe(ref.current);
    return () => observer.disconnect();
  }, [target]);

  return <span ref={ref}>{count}{suffix}</span>;
}

export default function StatsSection() {
  return (
    <section style={{
      background: "linear-gradient(135deg, #1e3a5f 0%, #0c2340 100%)",
      padding: "80px 0",
    }}>
      <div className="ws-container">
        <div className="ws-grid-4">
          {STATS.map((s, i) => (
            <motion.div key={s.label}
              initial={{ opacity: 0, y: 24 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.45, delay: i * 0.1 }}
              style={{ textAlign: "center", padding: "28px 16px" }}>
              <div style={{
                fontSize: "3.2rem", fontWeight: 900, color: "#0ea5e9",
                marginBottom: 10, lineHeight: 1,
              }}>
                <CountUp target={s.value} suffix={s.suffix} />
              </div>
              <div style={{ fontSize: "1rem", color: "#bfdbfe", fontWeight: 600 }}>
                {s.label}
              </div>
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
