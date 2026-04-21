import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { formatNumber } from "../../utils/formatters";

export default function TrendChart({
  mode,
  primaryRecords,
  comparisonRecords,
  primaryCountry,
  comparisonCountry,
  theme,
}) {
  const chartData =
    mode === "compare"
      ? buildComparisonChartData(primaryRecords, comparisonRecords)
      : buildSingleChartData(primaryRecords);

  const noPrimaryData = !primaryRecords || primaryRecords.length === 0;
  const noComparisonData =
    mode === "compare" &&
    (!comparisonRecords || comparisonRecords.length === 0);

  if (chartData.length === 0 || noPrimaryData) {
    return (
      <section className="panel">
        <div className="panel-header">
          <h2>{mode === "compare" ? "Case Trend Comparison" : "Case Trend"}</h2>
          <p>
            {mode === "compare"
              ? "Compare weekly detected cases across the selected countries."
              : "Track weekly detected cases for the selected country."}
          </p>
        </div>

        <div className="empty-state">
          <h3>No records found</h3>
          <p>
            No disease records were returned for the current selection. Try a
            different country or epidemiological week range.
          </p>
        </div>
      </section>
    );
  }

  const axisTickColor = theme === "dark" ? "#cbd5e1" : "#475569";
  const axisLineColor = theme === "dark" ? "rgba(148, 163, 184, 0.35)" : "#cbd5e1";
  const gridColor = theme === "dark" ? "rgba(148, 163, 184, 0.22)" : "rgba(148, 163, 184, 0.28)";
  const legendColor = theme === "dark" ? "#e2e8f0" : "#334155";
  const tooltipBackground = theme === "dark" ? "#0f172a" : "#ffffff";
  const tooltipBorder = theme === "dark" ? "#334155" : "#cbd5e1";
  const tooltipText = theme === "dark" ? "#f8fafc" : "#0f172a";
  const tooltipItem = theme === "dark" ? "#e2e8f0" : "#334155";

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>{mode === "compare" ? "Case Trend Comparison" : "Case Trend"}</h2>
        <p>
          {mode === "compare"
            ? `Compare weekly detected cases between ${primaryCountry} and ${comparisonCountry}.`
            : `Track weekly detected cases for ${primaryCountry} over the selected epidemiological period.`}
        </p>
      </div>

      {mode === "compare" && noComparisonData && (
        <div className="chart-note">
          No comparison records were returned for {comparisonCountry}. Only the
          primary country line may be visible.
        </div>
      )}

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={380}>
          <LineChart data={chartData}>
            <CartesianGrid stroke={gridColor} strokeDasharray="3 3" />
            <XAxis
              dataKey="epi_week"
              tick={{ fill: axisTickColor, fontSize: 12 }}
              stroke={axisLineColor}
            />
            <YAxis
              tick={{ fill: axisTickColor, fontSize: 12 }}
              stroke={axisLineColor}
            />
            <Tooltip
              formatter={(value) => formatNumber(value)}
              labelFormatter={(label) => `Week: ${label}`}
              contentStyle={{
                backgroundColor: tooltipBackground,
                border: `1px solid ${tooltipBorder}`,
                borderRadius: "12px",
                color: tooltipText,
              }}
              labelStyle={{ color: tooltipText, fontWeight: 700 }}
              itemStyle={{ color: tooltipItem }}
            />
            <Legend wrapperStyle={{ color: legendColor }} />
            <Line
              type="monotone"
              dataKey={primaryCountry}
              stroke="#3b82f6"
              strokeWidth={3}
              dot={false}
              activeDot={{ r: 5 }}
            />
            {mode === "compare" && (
              <Line
                type="monotone"
                dataKey={comparisonCountry}
                stroke="#a855f7"
                strokeWidth={3}
                dot={false}
                activeDot={{ r: 5 }}
              />
            )}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}

function buildSingleChartData(primaryRecords) {
  return primaryRecords
    .map((record) => {
      const week = record?.payload?.epi_week;
      const country = record?.payload?.country_code;
      const cases = Number(record?.payload?.cases_detected || 0);

      if (!week || !country) return null;

      return {
        epi_week: week,
        [country]: cases,
      };
    })
    .filter(Boolean)
    .sort((a, b) => String(a.epi_week).localeCompare(String(b.epi_week)));
}

function buildComparisonChartData(primaryRecords, comparisonRecords) {
  const dataMap = new Map();

  primaryRecords.forEach((record) => {
    const week = record?.payload?.epi_week;
    const country = record?.payload?.country_code;
    const cases = Number(record?.payload?.cases_detected || 0);

    if (!week || !country) return;

    if (!dataMap.has(week)) {
      dataMap.set(week, { epi_week: week });
    }

    dataMap.get(week)[country] = cases;
  });

  comparisonRecords.forEach((record) => {
    const week = record?.payload?.epi_week;
    const country = record?.payload?.country_code;
    const cases = Number(record?.payload?.cases_detected || 0);

    if (!week || !country) return;

    if (!dataMap.has(week)) {
      dataMap.set(week, { epi_week: week });
    }

    dataMap.get(week)[country] = cases;
  });

  return Array.from(dataMap.values()).sort((a, b) =>
    String(a.epi_week).localeCompare(String(b.epi_week))
  );
}