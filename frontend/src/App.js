import { BrowserRouter, Routes, Route, Navigate, useLocation } from "react-router-dom";
import { useEffect, useState } from "react";

// Auth context
import { AuthProvider } from "./context/AuthContext";

// Auth pages (unchanged)
import Login    from "./pages/Login";
import Register from "./pages/Register";

// Legacy full-page chatbot & documents (unchanged, still accessible)
import Chatbot   from "./pages/Chatbot";
import Documents from "./pages/Documents";

// Website pages
import Home          from "./pages/Home";
import About         from "./pages/About";
import ProductsPage  from "./pages/ProductsPage";
import ServicesPage  from "./pages/ServicesPage";
import ResourcesPage from "./pages/ResourcesPage";
import ContactPage   from "./pages/ContactPage";

// Website shell
import Navbar          from "./components/Navbar";
import Footer          from "./components/Footer";
import FloatingChatbot from "./components/FloatingChatbot";
import SessionTimeoutHandler from "./components/SessionTimeoutHandler";

import { supabase } from "./lib/supabase";

// ── Auth guard (unchanged logic) ──────────────────────────────────────────
function ProtectedRoute({ children }) {
  const [session, setSession]          = useState(null);
  const [checkingSession, setChecking] = useState(true);
  const location                       = useLocation();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setChecking(false);
    });
    const { data: listener } = supabase.auth.onAuthStateChange((_, s) => {
      setSession(s);
      setChecking(false);
    });
    return () => listener.subscription.unsubscribe();
  }, []);

  if (checkingSession) return null;
  if (!session) return <Navigate to="/login" replace state={{ from: location }} />;
  return children;
}

// ── Website layout wrapper ────────────────────────────────────────────────
function WebsiteLayout({ children }) {
  const [chatOpen, setChatOpen] = useState(false);
  const childWithProps = typeof children.type === "function"
    ? { ...children, props: { ...children.props, onOpenChat: () => setChatOpen(true) } }
    : children;

  return (
    <>
      <Navbar />
      {childWithProps}
      <Footer />
      <FloatingChatbot externalOpen={chatOpen} onExternalOpenHandled={() => setChatOpen(false)} />
    </>
  );
}

// ── App ───────────────────────────────────────────────────────────────────
function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        {/* Session timeout — only affects logged-in users; guests are excluded */}
        <SessionTimeoutHandler />
        <Routes>
          {/* Public website pages */}
          <Route path="/" element={<WebsiteLayout><Home /></WebsiteLayout>} />
          <Route path="/about" element={<WebsiteLayout><About /></WebsiteLayout>} />
          <Route path="/products" element={<WebsiteLayout><ProductsPage /></WebsiteLayout>} />
          <Route path="/services" element={<WebsiteLayout><ServicesPage /></WebsiteLayout>} />
          <Route path="/resources" element={<WebsiteLayout><ResourcesPage /></WebsiteLayout>} />
          <Route path="/contact" element={<WebsiteLayout><ContactPage /></WebsiteLayout>} />

          {/* Auth */}
          <Route path="/login"    element={<Login />} />
          <Route path="/register" element={<Register />} />

          {/* Protected legacy pages */}
          <Route path="/chat"      element={<ProtectedRoute><Chatbot /></ProtectedRoute>} />
          <Route path="/documents" element={<ProtectedRoute><Documents /></ProtectedRoute>} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}

export default App;
