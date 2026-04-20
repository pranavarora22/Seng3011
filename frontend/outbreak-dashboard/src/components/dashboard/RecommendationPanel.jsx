import { formatDecimal } from "../../utils/formatters";

export default function RecommendationPanel({ signal }) {
  const payload = signal?.payload;

  if (!payload) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>Recommended Action</h2>
          <p>No analytical recommendation is available for the current selection.</p>
        </div>
      </section>
    );
  }

  const recommendation = getRecommendation(payload);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Recommended Action</h2>
        <p>Operational interpretation of the current outbreak signal.</p>
      </div>

      <div className={`recommendation-card ${recommendation.toneClass}`}>
        <p className="recommendation-label">{recommendation.label}</p>
        <h3>{recommendation.title}</h3>
        <p className="recommendation-body">{recommendation.body}</p>

        <ul className="detail-list">
          <li>
            <strong>Risk level:</strong> {payload.risk_level || "N/A"}
          </li>
          <li>
            <strong>Growth rate:</strong> {formatDecimal(payload.growth_rate)}
          </li>
          <li>
            <strong>Seasonal z-score:</strong> {formatDecimal(payload.seasonal_z_score)}
          </li>
          <li>
            <strong>Persistence weeks:</strong> {payload.persistence_weeks ?? "N/A"}
          </li>
        </ul>
      </div>
    </section>
  );
}

function getRecommendation(payload) {
  const riskLevel = String(payload.risk_level || "").toLowerCase();
  const growthRate = Number(payload.growth_rate || 0);
  const zScore = Number(payload.seasonal_z_score || 0);
  const persistence = Number(payload.persistence_weeks || 0);

  if (
    riskLevel.includes("critical") ||
    riskLevel.includes("severe") ||
    (growthRate > 0.3 && zScore > 2.0 && persistence >= 2)
  ) {
    return {
      label: "Priority Recommendation",
      title: "Escalate Monitoring",
      body: "Indicators suggest unusually elevated activity. This region should be prioritised for closer review and short-term monitoring attention.",
      toneClass: "recommendation-critical",
    };
  }

  if (
    riskLevel.includes("high") ||
    riskLevel.includes("emerging") ||
    (growthRate > 0.1 && zScore > 1.0)
  ) {
    return {
      label: "Priority Recommendation",
      title: "Monitor Closely",
      body: "Signals indicate above-baseline activity. Maintain regular review and watch for further increases in persistence or growth.",
      toneClass: "recommendation-high",
    };
  }

  if (
    riskLevel.includes("medium") ||
    riskLevel.includes("elevated") ||
    zScore > 0.5
  ) {
    return {
      label: "Priority Recommendation",
      title: "Watch for Change",
      body: "The current signal is moderately elevated. Continue tracking this region to detect any upward shift in activity.",
      toneClass: "recommendation-medium",
    };
  }

  return {
    label: "Priority Recommendation",
    title: "Stable Trend",
    body: "Current indicators do not suggest unusual outbreak pressure. Continue routine monitoring without immediate escalation.",
    toneClass: "recommendation-low",
  };
}