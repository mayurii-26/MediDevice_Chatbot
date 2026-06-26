import { useEffect, useState } from "react";
import { Link, useNavigate, useLocation } from "react-router-dom";
import { supabase } from "../lib/supabase";

function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();
  const location = useLocation();
  const infoMessage = location.state?.message || null;

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        navigate("/");
      }
    });
  }, [navigate]);

  async function handleLogin(e) {
    e.preventDefault();
    setStatus("");
    setLoading(true);

    const { data, error } =
      await supabase.auth.signInWithPassword({
        email: email.trim(),
        password: password.trim(),
      });

    setLoading(false);

    if (error) {
      setStatus(error.message);
      return;
    }

    console.log(data);
    navigate("/");
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleLogin}>
        <div className="auth-brand">MediDevice Assistant</div>
        <h1>Login</h1>
        <p className="auth-subtitle">
          Sign in to continue to your saved conversations.
        </p>

        <label>Email</label>
        <input
          type="email"
          placeholder="you@example.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />

        <label>Password</label>
        <input
          type="password"
          placeholder="Enter your password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />

        {infoMessage && <p className="auth-status success">{infoMessage}</p>}
        {status && <p className="auth-status error">{status}</p>}

        <button className="auth-btn" type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>

        <p className="auth-switch">
          New here? <Link to="/register">Create an account</Link>
        </p>
      </form>
    </div>
  );
}

export default Login;
