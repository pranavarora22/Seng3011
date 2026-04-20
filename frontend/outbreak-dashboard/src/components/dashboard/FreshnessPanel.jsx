export default function FreshnessPanel({ mode }) {
  const now = new Date();

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>System Status</h2>
        <p>Trust and operational context for the dashboard.</p>
      </div>

      <div className="status-list">
        <div className="status-row">
          <span className="status-label">Source</span>
          <span className="status-value">WHO FluNet / NCOV</span>
        </div>

        <div className="status-row">
          <span className="status-label">Dashboard Status</span>
          <span className="status-value">Live</span>
        </div>

        <div className="status-row">
          <span className="status-label">View Mode</span>
          <span className="status-value">
            {mode === "compare" ? "Compare Countries" : "Single Country"}
          </span>
        </div>

        <div className="status-row">
          <span className="status-label">Last Viewed</span>
          <span className="status-value">{now.toLocaleString("en-AU", { timeZone: "Australia/Sydney" })}</span>
        </div>

        <div className="status-row">
          <span className="status-label">Output Type</span>
          <span className="status-value">Records + Risk Signals</span>
        </div>
      </div>

      <div className="method-note">
        <p className="method-note-label">Method Summary</p>
        <p className="method-note-text">
          Risk signals combine recent case activity, seasonal deviation, growth,
          acceleration, and persistence into a simplified outbreak score for
          faster monitoring decisions.
        </p>
      </div>
    </section>
  );
}