import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { supabase } from "../lib/supabase";

function Register() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  async function handleRegister(e) {
    e.preventDefault();
    setStatus("");
    setLoading(true);

    const { data, error } =
      await supabase.auth.signUp({
        email: email.trim(),
        password,
      });

    setLoading(false);

    if (error) {
      setStatus(error.message);
      return;
    }

    if (data.session) {
      navigate("/");
      return;
    }

    // Email confirmation is enabled — redirect to login after sign-up
    navigate("/login", { state: { message: "Account created. Please login." } });
  }

  return (
    <div className="auth-page">
      <form className="auth-card" onSubmit={handleRegister}>
        <div className="auth-brand">MediDevice Assistant</div>
        <h1>Create Account</h1>
        <p className="auth-subtitle">
          Register to save and reopen your chatbot history.
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
          placeholder="Create a password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          minLength="6"
          required
        />

        {status && (
          <p className={status.includes("successful") ? "auth-status success" : "auth-status error"}>
            {status}
          </p>
        )}

        <button className="auth-btn" type="submit" disabled={loading}>
          {loading ? "Creating account..." : "Register"}
        </button>

        <p className="auth-switch">
          Already have an account? <Link to="/login">Login</Link>
        </p>
      </form>
    </div>
  );
}

export default Register;
