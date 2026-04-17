import { useEffect, useState } from "react";
import FilterBar from "./components/FilterBar";
import SummaryCards from "./components/SummaryCards";
import TrendChart from "./components/TrendChart";
import RiskInsight from "./components/RiskInsight";
import LoadingState from "./components/LoadingState";
import ErrorState from "./components/ErrorState";
import {
  fetchDiseaseRecords,
  fetchAnalyticalSignal,
} from "./services/api";

export default function App() {
  const [filters, setFilters] = useState({
    disease: "influenza",
    country_code: "AUS",
    start_epi_week: "2024-W01",
    end_epi_week: "2024-W52",
    limit: 100,
  });

  const [records, setRecords] = useState([]);
  const [signal, setSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  async function loadDashboardData(activeFilters) {
    setLoading(true);
    setError("");

    try {
      const [retrievalResponse, analyticalResponse] = await Promise.all([
        fetchDiseaseRecords(activeFilters),
        fetchAnalyticalSignal({
          disease: activeFilters.disease,
          country_code: activeFilters.country_code,
        }),
      ]);

      const retrievedItems = extractRetrievalItems(retrievalResponse);
      const extractedSignal = extractAnalyticalSignal(analyticalResponse);

      setRecords(retrievedItems);
      setSignal(extractedSignal);
    } catch (err) {
      setRecords([]);
      setSignal(null);
      setError(err.message || "Failed to load dashboard data.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboardData(filters);
  }, []);

  function handleApplyFilters(newFilters) {
    setFilters(newFilters);
    loadDashboardData(newFilters);
  }

  return (
    <div className="app-shell">
      <header className="hero">
        <div>
          <p className="eyebrow">T18 Charlie</p>
          <h1>Outbreak Insight Dashboard</h1>
          <p className="hero-subtitle">
            Monitor disease trends and outbreak risk signals
          </p>
        </div>
      </header>

      <FilterBar filters={filters} onApply={handleApplyFilters} />

      {loading && <LoadingState />}
      {!loading && error && <ErrorState message={error} />}

      {!loading && !error && (
        <>
          <SummaryCards records={records} signal={signal} />
          <TrendChart records={records} />
          <RiskInsight signal={signal} />
        </>
      )}
    </div>
  );
}

function extractRetrievalItems(response) {
  if (Array.isArray(response)) {
    return response;
  }

  if (Array.isArray(response.items)) {
    return response.items;
  }

  if (Array.isArray(response.records)) {
    return response.records;
  }

  if (response.item && typeof response.item === "object") {
    return [response.item];
  }

  return [];
}

function extractAnalyticalSignal(response) {
  if (!response) {
    return null;
  }

  if (Array.isArray(response)) {
    return response[0] ?? null;
  }

  if (Array.isArray(response.items)) {
    return response.items[0] ?? null;
  }

  if (Array.isArray(response.signals)) {
    return response.signals[0] ?? null;
  }

  if (response.payload) {
    return response;
  }

  return response;
}