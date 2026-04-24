export default function LandingPage({ onGoLogin, onGoSignup, theme, onThemeToggle }) {
  const dark = theme === "dark";

  return (
    <div className={`landing ${dark ? "landing-dark" : ""}`}>

      {/* ── Navbar ── */}
      <nav className="landing-nav">
        <div className="landing-nav-brand">
          <img src="/logo.png" alt="BioRadar" className="landing-nav-logo" />
          <span className="landing-nav-name">BioRadar</span>
        </div>

        <div className="landing-nav-actions">
          <button
            className="landing-theme-btn"
            onClick={onThemeToggle}
            aria-label="Toggle dark mode"
            title={dark ? "Switch to light mode" : "Switch to dark mode"}
          >
            {dark ? "☀ Light" : "☾ Dark"}
          </button>
          <button className="landing-nav-signin" onClick={onGoLogin}>Sign in</button>
          <button className="landing-nav-signup" onClick={onGoSignup}>Sign up free</button>
        </div>
      </nav>

      {/* ── Hero ── */}
      <section className="landing-hero">
        <div className="landing-hero-badge">Live Disease Surveillance</div>
        <h1 className="landing-hero-title">
          Track outbreaks.<br />Act before they spread.
        </h1>
        <p className="landing-hero-sub">
          BioRadar turns WHO surveillance data into real-time risk signals
          for influenza, RSV, and SARS-CoV-2 across every country.
        </p>
        <div className="landing-hero-ctas">
          <button className="landing-cta-primary" onClick={onGoSignup}>
            Get started — it&apos;s free
          </button>
          <button className="landing-cta-secondary" onClick={onGoLogin}>
            Sign in to dashboard
          </button>
        </div>
      </section>

      {/* ── Features ── */}
      <section className="landing-features">
        <div className="landing-feature-card">
          <div className="landing-feature-icon">📡</div>
          <h3>Real-time signals</h3>
          <p>Z-score risk analysis updated weekly from live WHO FluMart and COVID datasets.</p>
        </div>
        <div className="landing-feature-card">
          <div className="landing-feature-icon">🌍</div>
          <h3>Global coverage</h3>
          <p>Compare disease trends across any two countries side-by-side with a single click.</p>
        </div>
        <div className="landing-feature-card">
          <div className="landing-feature-icon">🔒</div>
          <h3>Secure access</h3>
          <p>JWT-based authentication keeps your account and session protected at all times.</p>
        </div>
      </section>

      {/* ── Footer ── */}
      <footer className="landing-footer">
        <span>© 2026 BioRadar · SENG3011 Team Charlie</span>
      </footer>
    </div>
  );
}
