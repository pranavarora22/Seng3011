export default function Sidebar({
  activeSection,
  onSectionChange,
  mode,
  onModeChange,
  theme,
  onThemeToggle,
}) {
  const items = [
    { id: "overview", label: "Overview" },
    { id: "trends", label: "Disease Trends" },
    { id: "risk", label: "Risk Signals" },
    { id: "comparison", label: mode === "compare" ? "Comparison" : "Key Drivers" },
    { id: "export", label: "Exports" },
  ];

  return (
    <aside className="sidebar">
      <div className="brand">
        <img src="/logo.png" alt="BioRadar" className="brand-logo" />
        <h2>BioRadar</h2>
      </div>

      <div className="sidebar-live-badge">
        {mode === "compare" ? "Compare Mode Active" : "Single Country Mode"}
      </div>

      <div>
        <div className="sidebar-section-title">Appearance</div>
        <div className="theme-toggle-row">
          <span className="theme-toggle-label">Light</span>

          <button
            type="button"
            className={`theme-toggle ${theme === "dark" ? "is-dark" : ""}`}
            onClick={onThemeToggle}
            aria-label="Toggle dark mode"
            aria-pressed={theme === "dark"}
          >
            <span className="theme-toggle-track">
              <span className="theme-toggle-thumb" />
            </span>
          </button>

          <span className="theme-toggle-label">Dark</span>
        </div>
      </div>

      <div>
        <div className="sidebar-section-title">Dashboard</div>
        <div className="nav-list">
          {items.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${activeSection === item.id ? "active" : ""}`}
              onClick={() => onSectionChange(item.id)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <div className="sidebar-section-title">View Mode</div>
        <div className="nav-list">
          <button
            className={`nav-item ${mode === "single" ? "active" : ""}`}
            type="button"
            onClick={() => onModeChange("single")}
          >
            Single Country
          </button>
          <button
            className={`nav-item ${mode === "compare" ? "active" : ""}`}
            type="button"
            onClick={() => onModeChange("compare")}
          >
            Compare Countries
          </button>
        </div>
      </div>

      <div className="sidebar-footer-card">
        <h4>Why this matters</h4>
        <p>
          Identify unusual disease activity earlier and turn raw surveillance
          data into clearer operational insight.
        </p>
        <button className="secondary-button" type="button">
          Health Intelligence Ready
        </button>
      </div>
    </aside>
  );
}