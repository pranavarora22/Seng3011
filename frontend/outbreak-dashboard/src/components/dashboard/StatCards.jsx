import {
  formatNumber,
  getLatestRecord,
  getRiskBadgeClass,
} from "../../utils/formatters";

export default function StatCards({ records, signal }) {
  const latestRecord = getLatestRecord(records);

  const latestCases = latestRecord?.payload?.cases_detected;
  const latestWeek = latestRecord?.payload?.epi_week;
  const riskLevel = signal?.payload?.risk_level;
  const riskScore = signal?.payload?.risk_score;
  const countryCode =
    signal?.payload?.country_code || latestRecord?.payload?.country_code;
  const disease = signal?.payload?.disease || latestRecord?.payload?.disease;

  const growthRate = Number(signal?.payload?.growth_rate || 0);
  const persistenceWeeks = signal?.payload?.persistence_weeks;
  const zScore = Number(signal?.payload?.seasonal_z_score || 0);

  return (
    <section className="stat-grid">
      <article className="stat-card enhanced-stat-card">
        <div className="stat-card-top">
          <p className="stat-label">Latest Cases</p>
          <span className="stat-chip neutral-chip">Current week</span>
        </div>
        <h3>{formatNumber(latestCases)}</h3>
        <p className="stat-meta">{latestWeek || "No week available"}</p>
        <p className="stat-subtext">
          Latest observed weekly case count for the selected country.
        </p>
      </article>

      <article className="stat-card enhanced-stat-card">
        <div className="stat-card-top">
          <p className="stat-label">Risk Level</p>
          <span className={getRiskBadgeClass(riskLevel)}>
            {riskLevel || "N/A"}
          </span>
        </div>
        <h3>{countryCode || "N/A"}</h3>
        <p className="stat-meta">{disease || "No disease selected"}</p>
        <p className="stat-subtext">
          Current analytical severity classification for this region.
        </p>
      </article>

      <article className="stat-card enhanced-stat-card">
        <div className="stat-card-top">
          <p className="stat-label">Risk Score</p>
          <span className={`stat-chip ${getScoreToneClass(riskScore)}`}>
            {getScoreToneLabel(riskScore)}
          </span>
        </div>
        <h3>{formatNumber(riskScore)}</h3>
        <p className="stat-meta">Composite outbreak signal</p>
        <p className="stat-subtext">
          Combined score derived from baseline deviation, growth, and persistence.
        </p>
      </article>

      <article className="stat-card enhanced-stat-card">
        <div className="stat-card-top">
          <p className="stat-label">Trend Indicators</p>
          <span className={`trend-indicator ${getTrendToneClass(growthRate, zScore)}`}>
            {getTrendLabel(growthRate, zScore)}
          </span>
        </div>
        <h3>{formatNumber(growthRate)}</h3>
        <p className="stat-meta">
          Persistence: {formatNumber(persistenceWeeks)} week(s)
        </p>
        <p className="stat-subtext">
          Growth rate and recent persistence of elevated activity.
        </p>
      </article>
    </section>
  );
}

function getScoreToneClass(score) {
  const numeric = Number(score || 0);

  if (numeric >= 85) return "chip-critical";
  if (numeric >= 65) return "chip-high";
  if (numeric >= 35) return "chip-medium";
  return "chip-low";
}

function getScoreToneLabel(score) {
  const numeric = Number(score || 0);

  if (numeric >= 85) return "Critical";
  if (numeric >= 65) return "High";
  if (numeric >= 35) return "Moderate";
  return "Low";
}

function getTrendToneClass(growthRate, zScore) {
  if (growthRate > 0.2 || zScore > 2) return "trend-up";
  if (growthRate > 0.05 || zScore > 1) return "trend-watch";
  if (growthRate < 0) return "trend-down";
  return "trend-stable";
}

function getTrendLabel(growthRate, zScore) {
  if (growthRate > 0.2 || zScore > 2) return "↑ Rising";
  if (growthRate > 0.05 || zScore > 1) return "↗ Watch";
  if (growthRate < 0) return "↓ Softening";
  return "→ Stable";
}