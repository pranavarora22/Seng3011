import { useEffect, useMemo, useRef, useState } from "react";
import Sidebar from "./components/layout/Sidebar";
import Topbar from "./components/layout/Topbar";
import FiltersPanel from "./components/dashboard/FiltersPanel";
import StatCards from "./components/dashboard/StatCards";
import TrendChart from "./components/dashboard/TrendChart";
import RiskInsightPanel from "./components/dashboard/RiskInsightPanel";
import ComparisonPanel from "./components/dashboard/ComparisonPanel";
import FreshnessPanel from "./components/dashboard/FreshnessPanel";
import ExportPanel from "./components/dashboard/ExportPanel";
import RecommendationPanel from "./components/dashboard/RecommendationPanel";
import LoadingState from "./components/common/LoadingState";
import ErrorState from "./components/common/ErrorState";
import {
  fetchDiseaseRecords,
  fetchAnalyticalSignal,
} from "./services/api";

export default function App() {
  const [theme, setTheme] = useState("light");

  useEffect(() => {
    document.body.classList.toggle("theme-dark-body", theme === "dark");

    return () => {
      document.body.classList.remove("theme-dark-body");
    };
  }, [theme]);

  const [filters, setFilters] = useState({
    mode: "single",
    disease: "influenza",
    country_code: "AUS",
    compare_country_code: "USA",
    start_epi_week: "2024-W01",
    end_epi_week: "2024-W52",
    limit: 100,
  });

  const [activeSection, setActiveSection] = useState("overview");

  const [records, setRecords] = useState([]);
  const [signal, setSignal] = useState(null);
  const [comparisonRecords, setComparisonRecords] = useState([]);
  const [comparisonSignal, setComparisonSignal] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const overviewRef = useRef(null);
  const trendsRef = useRef(null);
  const riskRef = useRef(null);
  const comparisonRef = useRef(null);
  const exportRef = useRef(null);

  async function loadDashboardData(activeFilters) {
    setLoading(true);
    setError("");

    try {
      const baseRequests = [
        fetchDiseaseRecords({
          disease: activeFilters.disease,
          country_code: activeFilters.country_code,
          start_epi_week: activeFilters.start_epi_week,
          end_epi_week: activeFilters.end_epi_week,
          limit: activeFilters.limit,
        }),
        fetchAnalyticalSignal({
          disease: activeFilters.disease,
          country_code: activeFilters.country_code,
        }),
      ];

      const comparisonRequests =
        activeFilters.mode === "compare"
          ? [
              fetchDiseaseRecords({
                disease: activeFilters.disease,
                country_code: activeFilters.compare_country_code,
                start_epi_week: activeFilters.start_epi_week,
                end_epi_week: activeFilters.end_epi_week,
                limit: activeFilters.limit,
              }),
              fetchAnalyticalSignal({
                disease: activeFilters.disease,
                country_code: activeFilters.compare_country_code,
              }),
            ]
          : [Promise.resolve(null), Promise.resolve(null)];

      const [
        primaryRecordsResponse,
        primarySignalResponse,
        comparisonRecordsResponse,
        comparisonSignalResponse,
      ] = await Promise.all([...baseRequests, ...comparisonRequests]);

      setRecords(extractItems(primaryRecordsResponse));
      setSignal(extractSignal(primarySignalResponse));
      setComparisonRecords(extractItems(comparisonRecordsResponse));
      setComparisonSignal(extractSignal(comparisonSignalResponse));
    } catch (err) {
      setError(err.message || "Failed to load dashboard data.");
      setRecords([]);
      setSignal(null);
      setComparisonRecords([]);
      setComparisonSignal(null);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboardData(filters);
  }, [filters]);

  function handleApplyFilters(nextFilters) {
    setFilters(nextFilters);
    loadDashboardData(nextFilters);
  }

  function handleModeChange(nextMode) {
    const nextFilters = {
      ...filters,
      mode: nextMode,
    };
    setFilters(nextFilters);
    loadDashboardData(nextFilters);
  }

  function handleThemeToggle() {
    setTheme((prev) => (prev === "light" ? "dark" : "light"));
  }

  function handleSectionChange(sectionId) {
    setActiveSection(sectionId);

    const sectionMap = {
      overview: overviewRef,
      trends: trendsRef,
      risk: riskRef,
      comparison: comparisonRef,
      export: exportRef,
    };

    const targetRef = sectionMap[sectionId];
    if (targetRef?.current) {
      targetRef.current.scrollIntoView({
        behavior: "smooth",
        block: "start",
      });
    }
  }

  useEffect(() => {
    const sectionEntries = [
      { id: "overview", ref: overviewRef },
      { id: "trends", ref: trendsRef },
      { id: "risk", ref: riskRef },
      { id: "comparison", ref: comparisonRef },
      { id: "export", ref: exportRef },
    ];

    const observer = new IntersectionObserver(
      (entries) => {
        const visibleEntries = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio);

        if (visibleEntries.length === 0) return;

        const visibleId =
          visibleEntries[0].target.getAttribute("data-section-id");
        if (visibleId) {
          setActiveSection(visibleId);
        }
      },
      {
        root: null,
        rootMargin: "-20% 0px -55% 0px",
        threshold: [0.2, 0.4, 0.6],
      }
    );

    sectionEntries.forEach(({ ref }) => {
      if (ref.current) observer.observe(ref.current);
    });

    return () => {
      sectionEntries.forEach(({ ref }) => {
        if (ref.current) observer.unobserve(ref.current);
      });
      observer.disconnect();
    };
  }, [filters.mode, loading]);

  const pageSubtitle = useMemo(() => {
    return "Early-warning health intelligence for analysts, planners, and researchers.";
  }, []);

  return (
    <div className={`app-shell ${theme === "dark" ? "theme-dark" : ""}`}>
      <Sidebar
        activeSection={activeSection}
        onSectionChange={handleSectionChange}
        mode={filters.mode}
        onModeChange={handleModeChange}
        theme={theme}
        onThemeToggle={handleThemeToggle}
      />

      <main className="main-content">
        <Topbar
          title="Outbreak Insight"
          subtitle={pageSubtitle}
          disease={filters.disease}
          countryCode={filters.country_code}
        />

        <section
          className="hero-banner"
          ref={overviewRef}
          data-section-id="overview"
        >
          <div>
            <p className="hero-kicker">Public Health Intelligence</p>
            <h1>Track disease trends and identify elevated outbreak risk faster.</h1>
            <p className="hero-text">
              Explore weekly WHO-based disease records, assess outbreak risk,
              compare countries when needed, and interpret analytical outputs
              through a polished operational dashboard.
            </p>

            <div className="hero-stat-strip">
              <div className="hero-stat-item">
                <span className="hero-stat-value">3</span>
                <span className="hero-stat-label">Supported diseases</span>
              </div>
              <div className="hero-stat-item">
                <span className="hero-stat-value">
                  {filters.mode === "compare" ? "2" : "1"}
                </span>
                <span className="hero-stat-label">Country views active</span>
              </div>
              <div className="hero-stat-item">
                <span className="hero-stat-value">Live</span>
                <span className="hero-stat-label">WHO-based data workflow</span>
              </div>
            </div>
          </div>

          <div className="hero-highlight-card">
            <span className="mini-label">Primary Audience</span>
            <strong>Public health analysts and operational planners</strong>
            <p>
              Turn raw surveillance data into clear charts, signals, and faster
              monitoring decisions.
            </p>

            <div className="value-list">
              <div className="value-item">Early signal visibility</div>
              <div className="value-item">Country comparison mode</div>
              <div className="value-item">Export-ready outputs</div>
            </div>
          </div>
        </section>

        <div className="dashboard-grid">
          <div className="grid-span-8">
            <FiltersPanel filters={filters} onApply={handleApplyFilters} />
          </div>

          <div className="grid-span-4">
            <FreshnessPanel mode={filters.mode} />
          </div>
        </div>

        {loading && <LoadingState />}
        {!loading && error && <ErrorState message={error} />}

        {!loading && !error && (
          <>
            <div>
              <StatCards records={records} signal={signal} />
            </div>

            <div className="dashboard-grid">
              <div className="grid-span-8">
                <section className="panel value-panel">
                  <div className="panel-header">
                    <h2>Why teams use this dashboard</h2>
                    <p>
                      The product turns raw surveillance data into faster monitoring insight.
                    </p>
                  </div>

                  <div className="value-grid">
                    <div className="value-box">
                      <h3>Spot unusual activity sooner</h3>
                      <p>
                        Highlight elevated outbreak signals without manually
                        interpreting raw records week by week.
                      </p>
                    </div>

                    <div className="value-box">
                      <h3>Compare regions quickly</h3>
                      <p>
                        Switch between single-country and comparison mode to
                        understand relative disease activity more clearly.
                      </p>
                    </div>

                    <div className="value-box">
                      <h3>Support downstream analysis</h3>
                      <p>
                        Export filtered results for reporting, research, or
                        operational planning workflows.
                      </p>
                    </div>
                  </div>
                </section>
              </div>

              <div className="grid-span-4">
                <RecommendationPanel signal={signal} />
              </div>
            </div>

            <div
              className="dashboard-grid"
              ref={trendsRef}
              data-section-id="trends"
            >
              <div className="grid-span-8">
                <TrendChart
                  mode={filters.mode}
                  primaryRecords={records}
                  comparisonRecords={comparisonRecords}
                  primaryCountry={filters.country_code}
                  comparisonCountry={filters.compare_country_code}
                  theme={theme}
                />
              </div>

              <div
                className="grid-span-4"
                ref={riskRef}
                data-section-id="risk"
              >
                <RiskInsightPanel signal={signal} />
              </div>
            </div>

            {filters.mode === "compare" ? (
              <div
                className="dashboard-grid"
                ref={comparisonRef}
                data-section-id="comparison"
              >
                <div className="grid-span-7">
                  <ComparisonPanel
                    mode={filters.mode}
                    primaryCountry={filters.country_code}
                    comparisonCountry={filters.compare_country_code}
                    primarySignal={signal}
                    comparisonSignal={comparisonSignal}
                  />
                </div>

                <div
                  className="grid-span-5"
                  ref={exportRef}
                  data-section-id="export"
                >
                  <ExportPanel
                    records={records}
                    comparisonRecords={comparisonRecords}
                    disease={filters.disease}
                    primaryCountry={filters.country_code}
                    comparisonCountry={filters.compare_country_code}
                  />
                </div>
              </div>
            ) : (
              <div className="dashboard-grid">
                <div
                  className="grid-span-7"
                  ref={comparisonRef}
                  data-section-id="comparison"
                >
                  <ComparisonPanel
                    mode={filters.mode}
                    primaryCountry={filters.country_code}
                    primarySignal={signal}
                  />
                </div>

                <div
                  className="grid-span-5"
                  ref={exportRef}
                  data-section-id="export"
                >
                  <ExportPanel
                    records={records}
                    comparisonRecords={[]}
                    disease={filters.disease}
                    primaryCountry={filters.country_code}
                    comparisonCountry=""
                  />
                </div>
              </div>
            )}
          </>
        )}
      </main>
    </div>
  );
}

function extractItems(response) {
  if (!response) return [];
  if (Array.isArray(response)) return response;
  if (Array.isArray(response.items)) return response.items;
  if (Array.isArray(response.records)) return response.records;
  return [];
}

function extractSignal(response) {
  if (!response) return null;
  if (Array.isArray(response)) return response[0] ?? null;
  if (Array.isArray(response.items)) return response.items[0] ?? null;
  if (Array.isArray(response.signals)) return response.signals[0] ?? null;
  if (response.payload) return response;
  return response;
}