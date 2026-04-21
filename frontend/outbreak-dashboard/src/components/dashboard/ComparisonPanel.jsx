import React from "react";
import { formatNumber, getRiskBadgeClass } from "../../utils/formatters";
import { fetchGDP, fetchUnemployment } from "../../services/api";

export default function ComparisonPanel({
  mode,
  primaryCountry,
  comparisonCountry,
  primarySignal,
  comparisonSignal,
}) {

  // ADDED STATE (safe, isolated)
  const [showExternal, setShowExternal] = React.useState(false);
  const [gdpData, setGdpData] = React.useState(null);
  const [unemploymentData, setUnemploymentData] = React.useState(null);
  const [loadingExternal, setLoadingExternal] = React.useState(false);

  // ADDED HANDLER
  const handleToggleExternal = async () => {
    const newState = !showExternal;
    setShowExternal(newState);

    if (newState && !gdpData && !unemploymentData) {
      setLoadingExternal(true);

      try {
        const gdp = await fetchGDP({
          start: "2020-Q1",
          end: "2023-Q4",
        });

        const unemployment = await fetchUnemployment({
          start: "2020-01",
          end: "2023-12",
        });

        console.log("GDP:", gdp);
        console.log("Unemployment:", unemployment);

        setGdpData(gdp);
        setUnemploymentData(unemployment);
      } catch (err) {
        console.error("External API error:", err);
      }

      setLoadingExternal(false);
    }
  };

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

        {/* ADDED BUTTON */}
        <button onClick={handleToggleExternal}>
          {showExternal ? "Hide Economic Data" : "Compare with Economic Data"}
        </button>

        {/* ADDED DISPLAY */}
        {showExternal && (
          <ExternalDataBlock
            loading={loadingExternal}
            gdpData={gdpData}
            unemploymentData={unemploymentData}
          />
        )}

        <SingleCountryDriverPanel
          country={primaryCountry}
          payload={
            hasUsableSignal(primarySignal) ? primarySignal.payload : null
          }
        />
      </section>
    );
  }

  const primaryPayload = hasUsableSignal(primarySignal)
    ? primarySignal.payload
    : null;
  const comparisonPayload = hasUsableSignal(comparisonSignal)
    ? comparisonSignal.payload
    : null;

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

      {/* ADDED BUTTON */}
      <button onClick={handleToggleExternal}>
        {showExternal ? "Hide Economic Data" : "Compare with Economic Data"}
      </button>

      {/* ADDED DISPLAY */}
      {showExternal && (
        <ExternalDataBlock
          loading={loadingExternal}
          gdpData={gdpData}
          unemploymentData={unemploymentData}
        />
      )}

      <div className="comparison-summary">
        <strong>Quick read:</strong>{" "}
        {buildComparisonSummary(
          primaryCountry,
          primaryPayload,
          comparisonCountry,
          comparisonPayload,
        )}
      </div>

      <div className="split-grid">
        <ComparisonCard country={primaryCountry} payload={primaryPayload} />
        <ComparisonCard
          country={comparisonCountry}
          payload={comparisonPayload}
        />
      </div>
    </section>
  );
}

// ADDED COMPONENT (isolated, no interference)
function ExternalDataBlock({ loading, gdpData, unemploymentData }) {
  if (loading) return <p>Loading economic data...</p>;

  if (!gdpData && !unemploymentData)
    return <p>No economic data available</p>;

  return (
    <div className="external-data">
      <h4>External Economic Data</h4>

      <pre style={{ maxHeight: "200px", overflow: "auto" }}>
        {JSON.stringify({ gdpData, unemploymentData }, null, 2)}
      </pre>

      <p>GDP first value: {gdpData?.[0]?.value || "N/A"}</p>
      <p>
        Unemployment first value: {unemploymentData?.[0]?.value || "N/A"}
      </p>
    </div>
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
  comparisonPayload,
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

  const primaryScore = Number(primaryPayload.risk_score ?? 0);
  const comparisonScore = Number(comparisonPayload.risk_score ?? 0);

  if (primaryScore > comparisonScore) {
    return `${primaryCountry} currently shows a stronger outbreak signal than ${comparisonCountry}.`;
  }

  if (comparisonScore > primaryScore) {
    return `${comparisonCountry} currently shows a stronger outbreak signal than ${primaryCountry}.`;
  }

  return `${primaryCountry} and ${comparisonCountry} currently show similar risk scores.`;
}

function hasUsableSignal(signal) {
  const payload = signal?.payload;
  if (!payload) return false;
  if (payload.risk_level === "INSUFFICIENT_DATA") return false;
  return payload.risk_score !== undefined && payload.risk_score !== null;
}