import { useState } from "react";
import { login } from "../../services/auth";

export default function LoginPage({ onAuth, onGoSignup, onGoLanding, theme, onThemeToggle }) {
  const [form, setForm] = useState({ email: "", password: "" });
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const dark = theme === "dark";

  function handleChange(e) {
    setForm((f) => ({ ...f, [e.target.name]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const user = await login(form);
      onAuth(user);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={`auth-page ${dark ? "auth-dark" : ""}`}>

      {/* mini navbar */}
      <div className="auth-topbar">
        <button className="auth-back-btn" onClick={onGoLanding}>
          ← BioRadar
        </button>
        <button className="landing-theme-btn" onClick={onThemeToggle}>
          {dark ? "☀ Light" : "☾ Dark"}
        </button>
      </div>

      <div className="auth-card">
        <div className="auth-logo">
          <img src="/logo.png" alt="BioRadar" className="auth-logo-img" />
          <h1 className="auth-title">BioRadar</h1>
          <p className="auth-subtitle">Disease Surveillance Platform</p>
        </div>

        <h2 className="auth-heading">Sign in</h2>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <label className="auth-label">
            Email
            <input
              type="email"
              name="email"
              value={form.email}
              onChange={handleChange}
              className="auth-input"
              placeholder="you@example.com"
              required
              autoFocus
            />
          </label>

          <label className="auth-label">
            Password
            <input
              type="password"
              name="password"
              value={form.password}
              onChange={handleChange}
              className="auth-input"
              placeholder="••••••••"
              required
            />
          </label>

          <button type="submit" className="auth-btn" disabled={loading}>
            {loading ? "Signing in…" : "Sign in"}
          </button>
        </form>

        <p className="auth-switch">
          Don&apos;t have an account?{" "}
          <button className="auth-link-btn" onClick={onGoSignup}>
            Create one
          </button>
        </p>
      </div>
    </div>
  );
}
