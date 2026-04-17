import {
  formatNumber,
  getLatestRecord,
  getRiskBadgeClass,
} from "../utils/formatters";

export default function SummaryCards({ records, signal }) {
  const latestRecord = getLatestRecord(records);

  const latestCases = latestRecord?.payload?.cases_detected;
  const latestWeek = latestRecord?.payload?.epi_week;
  const riskLevel = signal?.payload?.risk_level;
  const riskScore = signal?.payload?.risk_score;
  const countryCode =
    signal?.payload?.country_code || latestRecord?.payload?.country_code;
  const disease = signal?.payload?.disease || latestRecord?.payload?.disease;

  return (
    <section className="summary-grid">
      <article className="panel stat-card">
        <p className="stat-label">Latest Cases</p>
        <h3>{formatNumber(latestCases)}</h3>
        <p className="stat-meta">{latestWeek || "No week available"}</p>
      </article>

      <article className="panel stat-card">
        <p className="stat-label">Risk Level</p>
        <h3>
          <span className={getRiskBadgeClass(riskLevel)}>
            {riskLevel || "N/A"}
          </span>
        </h3>
        <p className="stat-meta">
          {countryCode || "N/A"} · {disease || "N/A"}
        </p>
      </article>

      <article className="panel stat-card">
        <p className="stat-label">Risk Score</p>
        <h3>{formatNumber(riskScore)}</h3>
        <p className="stat-meta">Analytical signal output</p>
      </article>
    </section>
  );
}