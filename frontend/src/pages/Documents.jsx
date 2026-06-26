import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import axios from "axios";
import "../App.css";

const API = "http://127.0.0.1:8000";

function Documents() {
  const navigate = useNavigate();

  const [categories, setCategories]       = useState([]);
  const [subcategories, setSubcategories] = useState([]);
  const [documents, setDocuments]         = useState([]);
  const [activeCategory, setActiveCategory]       = useState(null);
  const [activeSubcategory, setActiveSubcategory] = useState(null);
  const [loadingCats, setLoadingCats]   = useState(true);
  const [loadingSubs, setLoadingSubs]   = useState(false);
  const [loadingDocs, setLoadingDocs]   = useState(false);
  const [pdfUrl, setPdfUrl]             = useState(null);   // modal state

  // Load categories on mount
  useEffect(() => {
    axios.get(`${API}/documents/categories`)
      .then(r => setCategories(r.data || []))
      .finally(() => setLoadingCats(false));
  }, []);

  // Load subcategories when category changes
  function selectCategory(cat) {
    setActiveCategory(cat);
    setActiveSubcategory(null);
    setDocuments([]);
    setLoadingSubs(true);
    axios.get(`${API}/documents/subcategories/${encodeURIComponent(cat)}`)
      .then(r => setSubcategories(r.data || []))
      .finally(() => setLoadingSubs(false));
  }

  // Load documents when subcategory changes
  function selectSubcategory(sub) {
    setActiveSubcategory(sub);
    setLoadingDocs(true);
    axios.get(`${API}/documents/list`, {
      params: { category: activeCategory, subcategory: sub }
    })
      .then(r => setDocuments(r.data || []))
      .finally(() => setLoadingDocs(false));
  }

  function handleDownload(url, name) {
    const a = document.createElement("a");
    a.href = url;
    a.download = name || "document.pdf";
    a.target = "_blank";
    a.rel = "noopener noreferrer";
    a.click();
  }

  return (
    <div className="doc-page">
      {/* Top nav */}
      <div className="doc-topnav">
        <span className="doc-brand">🏥 MediDevice Assistant</span>
        <div className="doc-nav-links">
          <button onClick={() => navigate("/")}>💬 Chatbot</button>
          <button className="active">📄 Documents</button>
        </div>
      </div>

      <div className="doc-layout">
        {/* ── Left: Categories ── */}
        <aside className="doc-panel">
          <div className="doc-panel-title">Categories</div>
          {loadingCats && <p className="doc-empty">Loading…</p>}
          {!loadingCats && categories.map(cat => (
            <button
              key={cat}
              className={`doc-panel-item${activeCategory === cat ? " active" : ""}`}
              onClick={() => selectCategory(cat)}
            >
              {cat}
            </button>
          ))}
        </aside>

        {/* ── Middle: Subcategories ── */}
        <aside className="doc-panel">
          <div className="doc-panel-title">Subcategories</div>
          {!activeCategory && <p className="doc-empty">Select a category.</p>}
          {activeCategory && loadingSubs && <p className="doc-empty">Loading…</p>}
          {activeCategory && !loadingSubs && subcategories.length === 0 && (
            <p className="doc-empty">No subcategories found.</p>
          )}
          {subcategories.map(sub => (
            <button
              key={sub}
              className={`doc-panel-item${activeSubcategory === sub ? " active" : ""}`}
              onClick={() => selectSubcategory(sub)}
            >
              {sub}
            </button>
          ))}
        </aside>

        {/* ── Right: Document Cards ── */}
        <section className="doc-main">
          <div className="doc-panel-title">
            {activeSubcategory
              ? `${activeCategory} › ${activeSubcategory}`
              : "Documents"}
          </div>

          {!activeSubcategory && <p className="doc-empty">Select a category and subcategory to view documents.</p>}
          {activeSubcategory && loadingDocs && <p className="doc-empty">Loading documents…</p>}
          {activeSubcategory && !loadingDocs && documents.length === 0 && (
            <p className="doc-empty">No documents found.</p>
          )}

          <div className="doc-cards">
            {documents.map(doc => (
              <div key={doc.id} className="doc-card">
                <div className="doc-card-type">{doc.document_type}</div>
                <div className="doc-card-name">{doc.document_name}</div>
                <div className="doc-card-product">📌 {doc.product_name}</div>
                <div className="doc-card-actions">
                  <button
                    className="doc-btn view"
                    onClick={() => setPdfUrl(doc.file_url)}
                  >
                    👁 View PDF
                  </button>
                  <button
                    className="doc-btn download"
                    onClick={() => handleDownload(doc.file_url, doc.document_name)}
                  >
                    ⬇ Download
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      </div>

      {/* ── PDF Modal ── */}
      {pdfUrl && (
        <div className="doc-modal-overlay" onClick={() => setPdfUrl(null)}>
          <div className="doc-modal" onClick={e => e.stopPropagation()}>
            <button className="doc-modal-close" onClick={() => setPdfUrl(null)}>✕</button>
            <iframe
              src={pdfUrl}
              title="PDF Viewer"
              className="doc-modal-iframe"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default Documents;
