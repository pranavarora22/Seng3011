import { useState } from "react";
import { signup } from "../../services/auth";

export default function SignupPage({ onAuth, onGoLogin, onGoLanding, theme, onThemeToggle }) {
  const [form, setForm] = useState({ name: "", email: "", password: "" });
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
      const user = await signup({ name: form.name, email: form.email, password: form.password });
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

        <h2 className="auth-heading">Create account</h2>

        {error && <div className="auth-error">{error}</div>}

        <form onSubmit={handleSubmit} className="auth-form" noValidate>
          <label className="auth-label">
            Name
            <input
              type="text"
              name="name"
              value={form.name}
              onChange={handleChange}
              className="auth-input"
              placeholder="Your name"
              autoFocus
            />
          </label>

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
            {loading ? "Creating account…" : "Create account"}
          </button>
        </form>

        <p className="auth-switch">
          Already have an account?{" "}
          <button className="auth-link-btn" onClick={onGoLogin}>
            Sign in
          </button>
        </p>
      </div>
    </div>
  );
}
