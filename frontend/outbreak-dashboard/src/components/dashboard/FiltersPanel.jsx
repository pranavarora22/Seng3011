import { useMemo, useState } from "react";
import COUNTRIES from "../../data/countries";
import { capitaliseDiseaseName } from "../../utils/formatters";

export default function FiltersPanel({ filters, onApply }) {
  const [localFilters, setLocalFilters] = useState(filters);
  const [syncedFilters, setSyncedFilters] = useState(filters);

  if (filters !== syncedFilters) {
    setSyncedFilters(filters);
    setLocalFilters(filters);
  }

  function handleChange(event) {
    const { name, value } = event.target;
    setLocalFilters((prev) => ({
      ...prev,
      [name]: name === "limit" ? Number(value) : value,
    }));
  }

  const duplicateCountrySelected =
    localFilters.mode === "compare" &&
    localFilters.country_code &&
    localFilters.compare_country_code &&
    localFilters.country_code === localFilters.compare_country_code;

  const canSubmit = !duplicateCountrySelected;

  function handleSubmit(event) {
    event.preventDefault();
    if (!canSubmit) return;
    onApply(localFilters);
  }

  const filteredComparisonCountries = useMemo(() => {
    if (localFilters.mode !== "compare") return COUNTRIES;
    return COUNTRIES.filter(
      (country) => country.code !== localFilters.country_code,
    );
  }, [localFilters.mode, localFilters.country_code]);

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Filters</h2>
        <p>
          Analyse one country by default, or switch to comparison mode for
          side-by-side regional analysis.
        </p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="mode-toggle">
          <label className="mode-option">
            <input
              type="radio"
              name="mode"
              value="single"
              checked={localFilters.mode === "single"}
              onChange={handleChange}
            />
            <span>Single Country</span>
          </label>

          <label className="mode-option">
            <input
              type="radio"
              name="mode"
              value="compare"
              checked={localFilters.mode === "compare"}
              onChange={handleChange}
            />
            <span>Compare Countries</span>
          </label>
        </div>

        <div className="filter-grid">
          <label className="field">
            <span>Disease</span>
            <select
              name="disease"
              value={localFilters.disease}
              onChange={handleChange}
            >
              <option value="influenza">
                {capitaliseDiseaseName("influenza")}
              </option>
              <option value="rsv">{capitaliseDiseaseName("rsv")}</option>
              <option value="sars-cov-2">
                {capitaliseDiseaseName("sars-cov-2")}
              </option>
            </select>
          </label>

          <label className="field">
            <span>Primary Country</span>
            <select
              name="country_code"
              value={localFilters.country_code}
              onChange={handleChange}
            >
              {COUNTRIES.map((country) => (
                <option key={country.code} value={country.code}>
                  {country.name} ({country.code})
                </option>
              ))}
            </select>
          </label>

          {localFilters.mode === "compare" ? (
            <label className="field">
              <span>Comparison Country</span>
              <select
                name="compare_country_code"
                value={localFilters.compare_country_code}
                onChange={handleChange}
              >
                {filteredComparisonCountries.map((country) => (
                  <option key={country.code} value={country.code}>
                    {country.name} ({country.code})
                  </option>
                ))}
              </select>
            </label>
          ) : (
            <label className="field">
              <span>View Type</span>
              <input type="text" value="Single-country analysis" readOnly />
            </label>
          )}

          <label className="field">
            <span>Start Epi Week</span>
            <input
              type="text"
              name="start_epi_week"
              value={localFilters.start_epi_week}
              onChange={handleChange}
              placeholder="2024-W01"
            />
          </label>

          <label className="field">
            <span>End Epi Week</span>
            <input
              type="text"
              name="end_epi_week"
              value={localFilters.end_epi_week}
              onChange={handleChange}
              placeholder="2024-W52"
            />
          </label>

          <label className="field">
            <span>Limit</span>
            <input
              type="number"
              name="limit"
              min="1"
              max="500"
              value={localFilters.limit}
              onChange={handleChange}
            />
          </label>
        </div>

        {duplicateCountrySelected && (
          <p className="inline-warning">
            Primary and comparison countries must be different.
          </p>
        )}

        <div className="filter-actions">
          <button
            type="submit"
            className="primary-button"
            disabled={!canSubmit}
          >
            Apply Filters
          </button>
        </div>
      </form>
    </section>
  );
}
