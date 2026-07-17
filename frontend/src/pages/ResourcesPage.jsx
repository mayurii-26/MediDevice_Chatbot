import { useEffect, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import axios from "axios";
import "../website.css";
import { Search, FileText, Eye, Download, FolderOpen, ChevronRight } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import DownloadModal from "../components/DownloadModal";

const API = "http://127.0.0.1:8000";

// ── Skeleton card ─────────────────────────────────────────────────────────
function SkeletonCard() {
  return (
    <div style={{
      background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
      padding: 28, animation: "ws-pulse 1.5s ease-in-out infinite",
    }}>
      <div style={{ width: 48, height: 48, borderRadius: 10, background: "#e2e8f0", marginBottom: 16 }} />
      <div style={{ height: 12, background: "#e2e8f0", borderRadius: 6, width: "40%", marginBottom: 10 }} />
      <div style={{ height: 18, background: "#e2e8f0", borderRadius: 6, width: "85%", marginBottom: 8 }} />
      <div style={{ height: 14, background: "#f1f5f9", borderRadius: 6, width: "60%", marginBottom: 20 }} />
      <div style={{ display: "flex", gap: 10 }}>
        <div style={{ height: 36, flex: 1, background: "#e2e8f0", borderRadius: 8 }} />
        <div style={{ height: 36, flex: 1, background: "#e2e8f0", borderRadius: 8 }} />
      </div>
    </div>
  );
}

// ── PDF Modal ─────────────────────────────────────────────────────────────
function PdfModal({ url, onClose }) {
  return (
    <AnimatePresence>
      {url && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
          onClick={onClose}
          style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.65)",
            display: "flex", alignItems: "center", justifyContent: "center",
            zIndex: 2000, padding: 24 }}>
          <motion.div
            initial={{ scale: 0.92, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.92, opacity: 0 }}
            transition={{ type: "spring", stiffness: 300, damping: 28 }}
            onClick={e => e.stopPropagation()}
            style={{ background: "#fff", borderRadius: 16, width: "100%", maxWidth: 960,
              height: "88vh", display: "flex", flexDirection: "column",
              overflow: "hidden", boxShadow: "0 24px 80px rgba(0,0,0,0.35)",
              position: "relative" }}>
            <button onClick={onClose} style={{
              position: "absolute", top: 12, right: 14, background: "#f1f5f9",
              border: "none", borderRadius: 8, width: 34, height: 34,
              cursor: "pointer", fontSize: "1rem", color: "#374151",
              display: "flex", alignItems: "center", justifyContent: "center",
              zIndex: 10, fontWeight: 700 }}>✕</button>
            <iframe src={url} title="PDF Viewer" style={{ flex: 1, border: "none" }} />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

// ── Document card ─────────────────────────────────────────────────────────
function DocCard({ doc, onView, onDownload }) {
  return (
    <motion.div whileHover={{ y: -4, boxShadow: "0 12px 40px rgba(30,58,95,0.14)" }}
      transition={{ duration: 0.18 }}
      style={{ background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
        padding: 28, display: "flex", flexDirection: "column",
        boxShadow: "0 2px 12px rgba(14,165,233,0.07)" }}>
      <div style={{ display: "flex", alignItems: "flex-start", gap: 14, marginBottom: 16 }}>
        <div style={{ width: 48, height: 48, borderRadius: 12, background: "#e0f2fe",
          display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
          <FileText size={22} color="#0ea5e9" />
        </div>
        <div style={{ minWidth: 0 }}>
          {doc.document_type && (
            <span style={{ display: "inline-block", background: "#e0f2fe", color: "#0ea5e9",
              fontSize: "0.72rem", fontWeight: 700, textTransform: "uppercase",
              letterSpacing: "0.5px", padding: "3px 10px", borderRadius: 20, marginBottom: 6 }}>
              {doc.document_type}
            </span>
          )}
          <div style={{ fontWeight: 700, color: "#1e3a5f", fontSize: "1rem",
            lineHeight: 1.35, wordBreak: "break-word" }}>
            {doc.document_name}
          </div>
        </div>
      </div>
      <div style={{ fontSize: "0.85rem", color: "#64748b", marginBottom: 20,
        display: "flex", alignItems: "center", gap: 6 }}>
        <span style={{ color: "#0ea5e9" }}>📌</span>{doc.product_name}
      </div>
      <div style={{ display: "flex", gap: 10, marginTop: "auto" }}>
        <button onClick={() => onView(doc.file_url)}
          style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            gap: 7, padding: "10px 14px", borderRadius: 8, border: "none",
            background: "#eff6ff", color: "#005eb8", fontWeight: 700,
            fontSize: "0.875rem", cursor: "pointer", transition: "background 0.15s" }}
          onMouseEnter={e => e.currentTarget.style.background = "#dbeafe"}
          onMouseLeave={e => e.currentTarget.style.background = "#eff6ff"}>
          <Eye size={15} /> View PDF
        </button>
        <button onClick={() => onDownload(doc)}
          style={{ flex: 1, display: "flex", alignItems: "center", justifyContent: "center",
            gap: 7, padding: "10px 14px", borderRadius: 8, border: "none",
            background: "#f0fdf4", color: "#15803d",
            fontWeight: 700, fontSize: "0.875rem", cursor: "pointer",
            transition: "background 0.15s" }}
          onMouseEnter={e => e.currentTarget.style.background = "#dcfce7"}
          onMouseLeave={e => e.currentTarget.style.background = "#f0fdf4"}>
          <Download size={15} /> Download
        </button>
      </div>
    </motion.div>
  );
}

// ── Main ResourcesPage ────────────────────────────────────────────────────
export default function ResourcesPage() {
  const { user, guestId } = useAuth();
  const [categories, setCategories]         = useState([]);
  const [subcategories, setSubcategories]   = useState([]);
  const [documents, setDocuments]           = useState([]);
  const [activeCategory, setActiveCategory] = useState(null);
  const [activeSub, setActiveSub]           = useState(null);
  const [search, setSearch]                 = useState("");
  const [loadingCats, setLoadingCats]       = useState(true);
  const [loadingSubs, setLoadingSubs]       = useState(false);
  const [loadingDocs, setLoadingDocs]       = useState(false);
  const [pdfUrl, setPdfUrl]                 = useState(null);
  // Download modal state
  const [downloadDoc, setDownloadDoc]       = useState(null);

  // Load categories on mount
  useEffect(() => {
    axios.get(`${API}/documents/categories`)
      .then(r => setCategories(r.data || []))
      .finally(() => setLoadingCats(false));
  }, []);

  function selectCategory(cat) {
    if (cat === activeCategory) return;
    setActiveCategory(cat);
    setActiveSub(null);
    setDocuments([]);
    setSearch("");
    setLoadingSubs(true);
    axios.get(`${API}/documents/subcategories/${encodeURIComponent(cat)}`)
      .then(r => setSubcategories(r.data || []))
      .finally(() => setLoadingSubs(false));
  }

  function selectSub(sub) {
    if (sub === activeSub) return;
    setActiveSub(sub);
    setSearch("");
    setLoadingDocs(true);
    axios.get(`${API}/documents/list`, {
      params: { category: activeCategory, subcategory: sub },
    })
      .then(r => setDocuments(r.data || []))
      .finally(() => setLoadingDocs(false));
  }

  // Client-side search filter
  const filtered = documents.filter(d =>
    !search.trim() ||
    d.document_name.toLowerCase().includes(search.toLowerCase()) ||
    (d.product_name || "").toLowerCase().includes(search.toLowerCase()) ||
    (d.document_type || "").toLowerCase().includes(search.toLowerCase())
  );

  return (
    <main style={{ paddingTop: 80, minHeight: "100vh", background: "#f8fafc" }}>

      {/* ── Page hero ── */}
      <section style={{
        background: "linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 60%, #f8fafc 100%)",
        padding: "72px 0 56px", borderBottom: "1px solid #e2e8f0",
      }}>
        <div className="ws-container" style={{ textAlign: "center" }}>
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}>
            <span className="ws-tag">Document Library</span>
            <h1 className="ws-heading" style={{ fontSize: "3rem", maxWidth: 700, margin: "0 auto 20px" }}>
              Medical Device Resources
            </h1>
            <p className="ws-subheading" style={{ margin: "0 auto 36px", textAlign: "center", fontSize: "1.15rem" }}>
              Browse brochures, datasheets, service manuals, and clinical guides
              for medical devices from leading manufacturers.
            </p>

            {/* Search bar */}
            <div style={{ position: "relative", maxWidth: 520, margin: "0 auto" }}>
              <Search size={18} color="#94a3b8" style={{
                position: "absolute", left: 16, top: "50%", transform: "translateY(-50%)",
                pointerEvents: "none",
              }} />
              <input
                type="text"
                placeholder="Search documents, products, or types…"
                value={search}
                onChange={e => setSearch(e.target.value)}
                style={{
                  width: "100%", padding: "15px 16px 15px 46px",
                  borderRadius: 12, border: "2px solid #e2e8f0",
                  fontSize: "1rem", fontFamily: "inherit",
                  background: "#fff", color: "#1e3a5f",
                  outline: "none", boxSizing: "border-box",
                  boxShadow: "0 4px 16px rgba(14,165,233,0.08)",
                  transition: "border-color 0.18s",
                }}
                onFocus={e => e.target.style.borderColor = "#0ea5e9"}
                onBlur={e => e.target.style.borderColor = "#e2e8f0"}
              />
            </div>
          </motion.div>
        </div>
      </section>

      <div className="ws-container" style={{ paddingTop: 48, paddingBottom: 80 }}>
        <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", gap: 32 }}
          className="resources-layout">

          {/* ── Left sidebar ── */}
          <aside>
            {/* Categories */}
            <div style={{
              background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
              overflow: "hidden", marginBottom: 20,
              boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
            }}>
              <div style={{
                padding: "14px 18px", borderBottom: "1px solid #f1f5f9",
                fontSize: "0.78rem", fontWeight: 800, textTransform: "uppercase",
                letterSpacing: "0.6px", color: "#0ea5e9",
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <FolderOpen size={14} /> Categories
              </div>
              {loadingCats
                ? [1, 2, 3, 4, 5].map(i => (
                    <div key={i} style={{ height: 40, margin: "6px 10px",
                      background: "#f1f5f9", borderRadius: 8,
                      animation: "ws-pulse 1.4s ease-in-out infinite" }} />
                  ))
                : categories.map(cat => (
                    <button key={cat} onClick={() => selectCategory(cat)} style={{
                      width: "100%", textAlign: "left", padding: "12px 18px",
                      background: activeCategory === cat ? "#e0f2fe" : "transparent",
                      border: "none", borderLeft: activeCategory === cat ? "3px solid #0ea5e9" : "3px solid transparent",
                      color: activeCategory === cat ? "#0ea5e9" : "#374151",
                      fontWeight: activeCategory === cat ? 700 : 500,
                      fontSize: "0.9rem", cursor: "pointer",
                      transition: "all 0.15s", display: "flex",
                      alignItems: "center", justifyContent: "space-between",
                    }}
                    onMouseEnter={e => { if (activeCategory !== cat) e.currentTarget.style.background = "#f8fafc"; }}
                    onMouseLeave={e => { if (activeCategory !== cat) e.currentTarget.style.background = "transparent"; }}>
                      {cat}
                      {activeCategory === cat && <ChevronRight size={14} color="#0ea5e9" />}
                    </button>
                  ))
              }
            </div>

            {/* Subcategories */}
            {activeCategory && (
              <motion.div
                initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}
                style={{
                  background: "#fff", borderRadius: 14, border: "1px solid #e2e8f0",
                  overflow: "hidden", boxShadow: "0 2px 8px rgba(0,0,0,0.05)",
                }}>
                <div style={{
                  padding: "14px 18px", borderBottom: "1px solid #f1f5f9",
                  fontSize: "0.78rem", fontWeight: 800, textTransform: "uppercase",
                  letterSpacing: "0.6px", color: "#0ea5e9",
                }}>
                  Subcategories
                </div>
                {loadingSubs
                  ? [1, 2, 3].map(i => (
                      <div key={i} style={{ height: 36, margin: "6px 10px",
                        background: "#f1f5f9", borderRadius: 8,
                        animation: "ws-pulse 1.4s ease-in-out infinite" }} />
                    ))
                  : subcategories.length === 0
                    ? <p style={{ padding: "14px 18px", color: "#94a3b8", fontSize: "0.875rem" }}>
                        No subcategories found.
                      </p>
                    : subcategories.map(sub => (
                        <button key={sub} onClick={() => selectSub(sub)} style={{
                          width: "100%", textAlign: "left", padding: "11px 18px",
                          background: activeSub === sub ? "#e0f2fe" : "transparent",
                          border: "none", borderLeft: activeSub === sub ? "3px solid #0ea5e9" : "3px solid transparent",
                          color: activeSub === sub ? "#0ea5e9" : "#374151",
                          fontWeight: activeSub === sub ? 700 : 500,
                          fontSize: "0.875rem", cursor: "pointer",
                          transition: "all 0.15s",
                        }}
                        onMouseEnter={e => { if (activeSub !== sub) e.currentTarget.style.background = "#f8fafc"; }}
                        onMouseLeave={e => { if (activeSub !== sub) e.currentTarget.style.background = "transparent"; }}>
                          {sub}
                        </button>
                      ))
                }
              </motion.div>
            )}
          </aside>

          {/* ── Document grid ── */}
          <section>
            {/* Breadcrumb */}
            <div style={{
              display: "flex", alignItems: "center", gap: 8,
              marginBottom: 24, fontSize: "0.875rem", color: "#64748b",
            }}>
              <span style={{ fontWeight: 600, color: "#1e3a5f" }}>Documents</span>
              {activeCategory && (<>
                <ChevronRight size={14} />
                <span style={{ color: activeCategory && !activeSub ? "#0ea5e9" : "#64748b",
                  fontWeight: activeCategory && !activeSub ? 700 : 400 }}>
                  {activeCategory}
                </span>
              </>)}
              {activeSub && (<>
                <ChevronRight size={14} />
                <span style={{ color: "#0ea5e9", fontWeight: 700 }}>{activeSub}</span>
              </>)}
              {filtered.length > 0 && (
                <span style={{ marginLeft: "auto", background: "#e0f2fe",
                  color: "#0ea5e9", padding: "3px 10px", borderRadius: 20,
                  fontSize: "0.78rem", fontWeight: 700 }}>
                  {filtered.length} document{filtered.length !== 1 ? "s" : ""}
                </span>
              )}
            </div>

            {/* Loading skeletons */}
            {loadingDocs && (
              <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill,minmax(280px,1fr))", gap: 20 }}>
                {[1, 2, 3, 4, 5, 6].map(i => <SkeletonCard key={i} />)}
              </div>
            )}

            {/* Empty — no selection */}
            {!loadingDocs && !activeSub && !search && (
              <div style={{ textAlign: "center", padding: "80px 24px" }}>
                <div style={{ fontSize: "4rem", marginBottom: 16 }}>📂</div>
                <h3 style={{ color: "#1e3a5f", fontWeight: 700, marginBottom: 8, fontSize: "1.25rem" }}>
                  Select a category to get started
                </h3>
                <p style={{ color: "#94a3b8", fontSize: "0.95rem" }}>
                  Choose a category from the sidebar to browse available documents.
                </p>
              </div>
            )}

            {/* Empty — no results for search */}
            {!loadingDocs && search && filtered.length === 0 && (
              <div style={{ textAlign: "center", padding: "80px 24px" }}>
                <div style={{ fontSize: "4rem", marginBottom: 16 }}>🔍</div>
                <h3 style={{ color: "#1e3a5f", fontWeight: 700, marginBottom: 8, fontSize: "1.25rem" }}>
                  No documents match "{search}"
                </h3>
                <p style={{ color: "#94a3b8", fontSize: "0.95rem" }}>
                  Try a different search term or browse by category.
                </p>
              </div>
            )}

            {/* Empty — subcategory selected but no docs */}
            {!loadingDocs && activeSub && documents.length === 0 && !search && (
              <div style={{ textAlign: "center", padding: "80px 24px" }}>
                <div style={{ fontSize: "4rem", marginBottom: 16 }}>📄</div>
                <h3 style={{ color: "#1e3a5f", fontWeight: 700, marginBottom: 8, fontSize: "1.25rem" }}>
                  No documents found
                </h3>
                <p style={{ color: "#94a3b8", fontSize: "0.95rem" }}>
                  No documents are available for this subcategory yet.
                </p>
              </div>
            )}

            {/* Document grid */}
            {!loadingDocs && filtered.length > 0 && (
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                style={{ display: "grid",
                  gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 20 }}>
                {filtered.map((doc, i) => (
                  <motion.div key={doc.id}
                    initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.05 }}>
                    <DocCard
                      doc={doc}
                      onView={setPdfUrl}
                      onDownload={setDownloadDoc}
                    />
                  </motion.div>
                ))}
              </motion.div>
            )}
          </section>
        </div>
      </div>

      {/* PDF Modal */}
      <PdfModal url={pdfUrl} onClose={() => setPdfUrl(null)} />

      {/* Secure Download Modal — OTP flow for everyone (guests + logged-in) */}
      <DownloadModal
        open={!!downloadDoc}
        onClose={() => setDownloadDoc(null)}
        document={downloadDoc}
        userId={user?.id || null}
        guestId={guestId || null}
      />

      <style>{`
        @keyframes ws-pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
        @media (max-width: 768px) {
          .resources-layout { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </main>
  );
}
