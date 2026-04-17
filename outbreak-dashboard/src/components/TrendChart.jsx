import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { formatNumber } from "../utils/formatters";

export default function TrendChart({ records }) {
  const chartData = records.map((record) => ({
    epi_week: record?.payload?.epi_week || "Unknown",
    cases_detected: Number(record?.payload?.cases_detected || 0),
  }));

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Case Trend</h2>
        <p>Weekly cases detected across the selected epidemiological range.</p>
      </div>

      <div className="chart-wrapper">
        <ResponsiveContainer width="100%" height={360}>
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="epi_week" />
            <YAxis />
            <Tooltip
              formatter={(value) => formatNumber(value)}
              labelFormatter={(label) => `Week: ${label}`}
            />
            <Line
              type="monotone"
              dataKey="cases_detected"
              strokeWidth={3}
              dot={false}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </section>
  );
}