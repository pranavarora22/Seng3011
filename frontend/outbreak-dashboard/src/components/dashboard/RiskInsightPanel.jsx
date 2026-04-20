import { formatDecimal, formatNumber } from "../../utils/formatters";

export default function RiskInsightPanel({ signal }) {
  const payload = signal?.payload;

  if (!payload) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>Risk Insight</h2>
          <p>No analytical signal is available for the current selection.</p>
        </div>
      </section>
    );
  }

  const explanation = buildExplanation(payload);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Risk Insight</h2>
        <p>Plain-English interpretation of the analytical signal.</p>
      </div>

      <div className="split-grid">
        <div>
          <h3>Summary</h3>
          <p className="insight-text">{explanation}</p>
        </div>

        <div>
          <h3>Signal Details</h3>
          <ul className="detail-list">
            <li>
              <strong>Current Cases:</strong>{" "}
              {formatNumber(payload.current_cases)}
            </li>
            <li>
              <strong>Seasonal Mean:</strong>{" "}
              {formatDecimal(payload.seasonal_mean)}
            </li>
            <li>
              <strong>Seasonal Std Dev:</strong>{" "}
              {formatDecimal(payload.seasonal_std_dev)}
            </li>
            <li>
              <strong>Seasonal Z Score:</strong>{" "}
              {formatDecimal(payload.seasonal_z_score)}
            </li>
            <li>
              <strong>Growth Rate:</strong>{" "}
              {formatDecimal(payload.growth_rate)}
            </li>
            <li>
              <strong>Acceleration:</strong>{" "}
              {formatDecimal(payload.acceleration)}
            </li>
            <li>
              <strong>Persistence Weeks:</strong>{" "}
              {formatNumber(payload.persistence_weeks)}
            </li>
            <li>
              <strong>Risk Score:</strong> {formatNumber(payload.risk_score)}
            </li>
          </ul>
        </div>
      </div>
    </section>
  );
}

function buildExplanation(payload) {
  const riskLevel = payload.risk_level || "unknown";
  const currentCases = formatNumber(payload.current_cases);
  const zScore = formatDecimal(payload.seasonal_z_score);
  const growthRate = formatDecimal(payload.growth_rate);
  const persistenceWeeks = formatNumber(payload.persistence_weeks);

  return `Risk is currently ${riskLevel}. The latest signal reports ${currentCases} cases, with a seasonal z-score of ${zScore}, a growth rate of ${growthRate}, and elevated activity persisting for ${persistenceWeeks} week(s).`;
}