import {
  downloadCsvFile,
  downloadJsonFile,
} from "../../utils/exporters";
import { capitaliseDiseaseName } from "../../utils/formatters";

export default function ExportPanel({
  records,
  comparisonRecords,
  disease,
  primaryCountry,
  comparisonCountry,
}) {
  const primary = records || [];
  const comparison = comparisonRecords || [];
  const totalRecords = primary.length + comparison.length;
  const hasData = totalRecords > 0;

  function handleDownloadJson() {
    if (!hasData) return;

    downloadJsonFile(
      `${disease}-${primaryCountry}${comparisonCountry ? `-${comparisonCountry}` : ""}-records.json`,
      {
        primary,
        comparison,
      }
    );
  }

  function handleDownloadCsv() {
    if (!hasData) return;

    const rows = [
      ...flattenRecords(primary),
      ...flattenRecords(comparison),
    ];

    downloadCsvFile(
      `${disease}-${primaryCountry}${comparisonCountry ? `-${comparisonCountry}` : ""}-records.csv`,
      rows
    );
  }

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Export Data</h2>
        <p>
          Download filtered disease records for downstream analytics,
          documentation, and reporting.
        </p>
      </div>

      <div className="export-summary">
        <p>
          <strong>Disease:</strong> {capitaliseDiseaseName(disease)}
        </p>
        <p>
          <strong>Primary country:</strong> {primaryCountry}
        </p>
        {comparisonCountry ? (
          <p>
            <strong>Comparison country:</strong> {comparisonCountry}
          </p>
        ) : (
          <p>
            <strong>View:</strong> Single-country analysis
          </p>
        )}
        <p>
          <strong>Total records selected:</strong> {totalRecords}
        </p>
      </div>

      {!hasData ? (
        <div className="empty-state">
          <h3>No records available to export</h3>
          <p>
            Try adjusting the selected country, disease, or epidemiological week
            range before exporting.
          </p>
        </div>
      ) : null}

      <div className="export-actions">
        <button
          className="primary-button"
          onClick={handleDownloadJson}
          disabled={!hasData}
        >
          Download JSON
        </button>
        <button
          className="ghost-button"
          onClick={handleDownloadCsv}
          disabled={!hasData}
        >
          Download CSV
        </button>
      </div>

      <p className="export-note">
        Exported files include the currently loaded records visible in this dashboard.
      </p>
    </section>
  );
}

function flattenRecords(records = []) {
  return records.map((record) => ({
    disease: record?.payload?.disease || "",
    country_code: record?.payload?.country_code || "",
    epi_week: record?.payload?.epi_week || "",
    cases_detected: record?.payload?.cases_detected || "",
  }));
}