import React, { useCallback, useEffect, useState, useRef } from "react";
import axios from "axios";
import { useNavigate } from "react-router-dom";
import "../App.css";
import ReactMarkdown from "react-markdown";
import SuggestedQuestions from "../components/SuggestedQuestions";
import CategoryDropdown from "../components/CategoryDropdown";
import VoiceInput from "../components/VoiceInput";
import ContactForm from "../components/ContactForm";
import LogoutButton from "../components/LogoutButton";
import { supabase } from "../lib/supabase";
import { isPurchaseIntent, PURCHASE_INTENT_REPLY } from "../lib/purchaseIntentDetector";

const API_BASE_URL = "http://127.0.0.1:8000";

const FALLBACK_MESSAGE =
  "I am a medical device assistant trained on medical device knowledge. " +
  "Please ask about supported medical devices. " +
  "For further assistance contact support@medideviceai.com";

function Chatbot() {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [activeCategory, setActiveCategory] = useState(null);
  const [session, setSession] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [activeConversationId, setActiveConversationId] = useState(null);
  const [historyLoading, setHistoryLoading] = useState(false);
  const [pdfUrl, setPdfUrl] = useState(null);
  const contactFormRef = useRef(null); // for scrolling to contact form on purchase intent

  const navigate = useNavigate();
  const user = session?.user || null;

  const authHeaders = useCallback(async () => {
    const { data } = await supabase.auth.getSession();
    const token = data.session?.access_token;
    return token ? { Authorization: `Bearer ${token}` } : {};
  }, []);

  const loadConversations = useCallback(async () => {
    if (!user?.id) {
      setConversations([]);
      return;
    }

    setHistoryLoading(true);
    try {
      const headers = await authHeaders();
      const response = await axios.get(`${API_BASE_URL}/history/${user.id}`, {
        headers,
      });
      console.log("History loaded", response.data);
      setConversations(response.data || []);
    } catch (error) {
      console.error("Failed to load history", error);
      setConversations([]);
    } finally {
      setHistoryLoading(false);
    }
  }, [authHeaders, user?.id]);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        if (!nextSession) {
          setConversations([]);
          setActiveConversationId(null);
        }
      }
    );

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const startNewChat = () => {
    setActiveConversationId(null);
    setMessages([]);
    setQuestion("");
  };

  const loadConversation = async (conversationId) => {
    if (!user?.id) return;

    setActiveConversationId(conversationId);
    setLoading(true);
    try {
      const headers = await authHeaders();
      const response = await axios.get(
        `${API_BASE_URL}/conversation/${conversationId}`,
        { headers }
      );
      console.log("Conversation loaded", response.data);

      setMessages(
        (response.data || []).map((message) => ({
          type: message.sender === "user" ? "user" : "bot",
          text: message.content,
        }))
      );
    } catch (error) {
      console.error("Failed to load conversation", error);
    } finally {
      setLoading(false);
    }
  };

  const askQuestion = async () => {
    if (!question.trim()) return;

    const userQuestion = question.trim();
    setMessages((prev) => [...prev, { type: "user", text: userQuestion }]);
    setQuestion("");
    setLoading(true);

    // ── Purchase / price / quote intent — short-circuit BEFORE retrieval ──
    if (isPurchaseIntent(userQuestion)) {
      setMessages((prev) => [
        ...prev,
        { type: "bot", text: PURCHASE_INTENT_REPLY, isPurchaseIntent: true },
      ]);
      setLoading(false);
      // Scroll the existing ContactForm into view
      setTimeout(() => {
        contactFormRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
      }, 150);
      return; // Do NOT call FAISS / BM25 / Gemini / backend
    }
    // ─────────────────────────────────────────────────────────────────────

    try {
      const headers = await authHeaders();
      const response = await axios.post(
        `${API_BASE_URL}/chat`,
        {
          question: userQuestion,
          user_id: user?.id || null,
          conversation_id: activeConversationId,
        },
        { headers, timeout: 30000 }
      );
      console.log("Chat response", response.data);

      const answer = response.data?.answer?.trim() || FALLBACK_MESSAGE;
      const source = response.data?.source || null;
      const product = response.data?.matched_product || null;
      const category = response.data?.matched_category || null;
      const confidence = response.data?.confidence ?? null;
      const documents = response.data?.documents || [];
      const conversationId = response.data?.conversation_id || activeConversationId;

      if (conversationId) {
        setActiveConversationId(conversationId);
      }

      setMessages((prev) => [
        ...prev,
        { type: "bot", text: answer, source, product, category, confidence, documents },
      ]);

      if (user?.id) {
        loadConversations();
      }
    } catch (error) {
      const serverMessage =
        error.response?.data?.detail ||
        error.response?.data?.answer ||
        null;

      setMessages((prev) => [
        ...prev,
        { type: "bot", text: serverMessage || FALLBACK_MESSAGE },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      askQuestion();
    }
  };

  return (
    <>
    <div className="chat-layout">
      <aside className="history-sidebar">
        <button className="new-chat-btn" onClick={startNewChat}>
          + New Chat
        </button>

        <div className="history-header">History</div>

        {!user && (
          <p className="history-empty">
            Login to view saved conversations.
          </p>
        )}

        {user && historyLoading && (
          <p className="history-empty">Loading history...</p>
        )}

        {user && !historyLoading && conversations.length === 0 && (
          <p className="history-empty">No conversations yet.</p>
        )}

        {user && conversations.map((conversation) => (
          <button
            key={conversation.id}
            className={
              conversation.id === activeConversationId
                ? "history-item active"
                : "history-item"
            }
            onClick={() => loadConversation(conversation.id)}
          >
            {conversation.title}
          </button>
        ))}

        {user && (
          <div className="sidebar-footer">
            <button onClick={() => navigate("/documents")}>📄 Documents</button>
            <LogoutButton />
          </div>
        )}
      </aside>

      <main className="app">
        <div className="header">
          <h1>🏥 MediDevice Assistant</h1>
          <p>AI Medical Knowledge Platform</p>
        </div>

        <div className="section">
          <h3>Browse by Category</h3>
          <CategoryDropdown setQuestion={setQuestion} onCategoryChange={setActiveCategory} />
        </div>

        <div className="section">
          <h3>Voice Input</h3>
          <VoiceInput setQuestion={setQuestion} />
        </div>

        <div className="section">
          <h3>Suggested Questions</h3>
          <SuggestedQuestions onSelect={setQuestion} activeCategory={activeCategory} />
        </div>

        <div className="section">
          <textarea
            rows="3"
            placeholder="Ask about medical devices..."
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            onKeyDown={handleKeyDown}
          />
          <br />
          <button
            className="ask-btn"
            onClick={askQuestion}
            disabled={loading}
          >
            {loading ? "Thinking..." : "Ask"}
          </button>
        </div>

        <div className="chat-container">
          <h2>Conversation</h2>

          <div className="chat-box">
            {messages.length === 0 && (
              <p className="empty-chat">
                Ask a question above to get started.
              </p>
            )}

            {messages.map((msg, index) => (
              <div
                key={index}
                className={msg.type === "user" ? "user-msg" : "bot-msg"}
              >
                <span className="msg-label">
                  {msg.type === "user" ? "You" : "Assistant"}
                </span>

                {msg.type === "bot" && msg.source && (
                  <div className="source-badge-row">
                    <span className={`source-badge source-${msg.source}`}>
                      {msg.source === "faiss" && "📦 Knowledge Base"}
                      {msg.source === "dynamic_search" && "🌐 Web Search"}
                      {msg.source === "fallback" && "⚠️ Fallback"}
                      {msg.source === "cache" && "Cached Answer"}
                    </span>
                    {msg.product && (
                      <span className="source-product">📌 {msg.product}</span>
                    )}
                    {msg.category && (
                      <span className="source-category">🏷️ {msg.category}</span>
                    )}
                    {msg.confidence !== null && msg.confidence > 0 && (
                      <span className="source-confidence">
                        🎯 {Math.round(msg.confidence * 100)}%
                      </span>
                    )}
                  </div>
                )}

                <ReactMarkdown>{msg.text}</ReactMarkdown>

                {msg.type === "bot" && msg.documents?.length > 0 && (
                  <div className="doc-rec-panel">
                    <div className="doc-rec-title">📄 Available Documents</div>
                    {msg.documents.map((doc) => (
                      <div key={doc.id} className="doc-rec-item">
                        <div className="doc-rec-info">
                          <span className="doc-rec-name">{doc.document_name}</span>
                          {doc.document_type && (
                            <span className="doc-rec-type">{doc.document_type}</span>
                          )}
                        </div>
                        <div className="doc-rec-actions">
                          <button
                            className="doc-rec-btn view"
                            onClick={() => setPdfUrl(doc.file_url)}
                          >
                            View
                          </button>
                          <a
                            className="doc-rec-btn download"
                            href={doc.file_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            download
                          >
                            Download
                          </a>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ))}

            {loading && (
              <div className="bot-msg">
                <span className="msg-label">Assistant</span>
                <p className="typing">Searching knowledge base...</p>
              </div>
            )}
          </div>
        </div>

        <ContactForm ref={contactFormRef} />
      </main>
    </div>

    {pdfUrl && (
      <div className="doc-modal-overlay" onClick={() => setPdfUrl(null)}>
        <div className="doc-modal" onClick={(e) => e.stopPropagation()}>
          <button className="doc-modal-close" onClick={() => setPdfUrl(null)}>✕</button>
          <iframe src={pdfUrl} title="PDF Viewer" className="doc-modal-iframe" />
        </div>
      </div>
    )}
    </>
  );
}

export default Chatbot;
