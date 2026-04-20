import {
  formatNumber,
  getRiskBadgeClass,
} from "../../utils/formatters";

export default function ComparisonPanel({
  mode,
  primaryCountry,
  comparisonCountry,
  primarySignal,
  comparisonSignal,
}) {
  if (mode !== "compare") {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>Key Signal Drivers</h2>
          <p>
            Single-country view focuses on the selected region’s most important
            outbreak indicators.
          </p>
        </div>

        <SingleCountryDriverPanel
          country={primaryCountry}
          payload={primarySignal?.payload}
        />
      </section>
    );
  }

  const primaryPayload = primarySignal?.payload;
  const comparisonPayload = comparisonSignal?.payload;

  if (!primaryPayload && !comparisonPayload) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>Country Comparison</h2>
          <p>
            Compare analytical outbreak signals between the selected regions.
          </p>
        </div>

        <div className="empty-state">
          <h3>No comparison signals available</h3>
          <p>
            Neither country returned an analytical signal for the current
            selection. Try another date range or country combination.
          </p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Country Comparison</h2>
        <p>
          Compare analytical outbreak signals between the selected primary and
          comparison regions.
        </p>
      </div>

      <div className="comparison-summary">
        <strong>Quick read:</strong>{" "}
        {buildComparisonSummary(primaryCountry, primaryPayload, comparisonCountry, comparisonPayload)}
      </div>

      <div className="split-grid">
        <ComparisonCard country={primaryCountry} payload={primaryPayload} />
        <ComparisonCard country={comparisonCountry} payload={comparisonPayload} />
      </div>
    </section>
  );
}

function ComparisonCard({ country, payload }) {
  if (!payload) {
    return (
      <div className="comparison-card-empty">
        <h3>{country}</h3>
        <p className="muted-text">No analytical signal available.</p>
      </div>
    );
  }

  return (
    <div className="comparison-card-filled">
      <h3>{country}</h3>
      <p>
        <span className={getRiskBadgeClass(payload.risk_level)}>
          {payload.risk_level || "N/A"}
        </span>
      </p>
      <ul className="detail-list">
        <li>
          <strong>Risk Score:</strong> {formatNumber(payload.risk_score)}
        </li>
        <li>
          <strong>Current Cases:</strong> {formatNumber(payload.current_cases)}
        </li>
        <li>
          <strong>Persistence:</strong>{" "}
          {formatNumber(payload.persistence_weeks)} week(s)
        </li>
      </ul>
    </div>
  );
}

function SingleCountryDriverPanel({ country, payload }) {
  if (!payload) {
    return (
      <div className="empty-state">
        <h3>No analytical signal available</h3>
        <p>
          No signal was returned for {country}. Try a different week range or
          supported disease selection.
        </p>
      </div>
    );
  }

  return (
    <div className="comparison-card-filled">
      <h3>{country}</h3>
      <p>
        <span className={getRiskBadgeClass(payload.risk_level)}>
          {payload.risk_level || "N/A"}
        </span>
      </p>
      <ul className="detail-list">
        <li>
          <strong>Risk Score:</strong> {formatNumber(payload.risk_score)}
        </li>
        <li>
          <strong>Current Cases:</strong> {formatNumber(payload.current_cases)}
        </li>
        <li>
          <strong>Growth Rate:</strong> {formatNumber(payload.growth_rate)}
        </li>
        <li>
          <strong>Persistence:</strong>{" "}
          {formatNumber(payload.persistence_weeks)} week(s)
        </li>
      </ul>
    </div>
  );
}

function buildComparisonSummary(
  primaryCountry,
  primaryPayload,
  comparisonCountry,
  comparisonPayload
) {
  if (!primaryPayload && comparisonPayload) {
    return `${comparisonCountry} returned a signal, while ${primaryCountry} did not.`;
  }

  if (primaryPayload && !comparisonPayload) {
    return `${primaryCountry} returned a signal, while ${comparisonCountry} did not.`;
  }

  if (!primaryPayload && !comparisonPayload) {
    return "No signals available for either selected country.";
  }

  const primaryScore = Number(primaryPayload.risk_score || 0);
  const comparisonScore = Number(comparisonPayload.risk_score || 0);

  if (primaryScore > comparisonScore) {
    return `${primaryCountry} currently shows a stronger outbreak signal than ${comparisonCountry}.`;
  }

  if (comparisonScore > primaryScore) {
    return `${comparisonCountry} currently shows a stronger outbreak signal than ${primaryCountry}.`;
  }

  return `${primaryCountry} and ${comparisonCountry} currently show similar risk scores.`;
}