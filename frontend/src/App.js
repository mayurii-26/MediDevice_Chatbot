import {
  BrowserRouter,
  Navigate,
  Routes,
  Route,
  useLocation
} from "react-router-dom";
import { useEffect, useState } from "react";

import Login from "./pages/Login";
import Register from "./pages/Register";
import Chatbot from "./pages/Chatbot";
import Documents from "./pages/Documents";
import { supabase } from "./lib/supabase";

function ProtectedRoute({ children }) {
  const [session, setSession] = useState(null);
  const [checkingSession, setCheckingSession] = useState(true);
  const location = useLocation();

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setCheckingSession(false);
    });

    const { data: listener } = supabase.auth.onAuthStateChange(
      (_event, nextSession) => {
        setSession(nextSession);
        setCheckingSession(false);
      }
    );

    return () => {
      listener.subscription.unsubscribe();
    };
  }, []);

  if (checkingSession) {
    return null;
  }

  if (!session) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  return children;
}

function App() {
  return (
    <BrowserRouter>

      <Routes>

        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Chatbot />
            </ProtectedRoute>
          }
        />

        <Route
          path="/login"
          element={<Login />}
        />

        <Route
          path="/register"
          element={<Register />}
        />

        <Route
          path="/documents"
          element={
            <ProtectedRoute>
              <Documents />
            </ProtectedRoute>
          }
        />

      </Routes>

    </BrowserRouter>
  );
}

export default App;
