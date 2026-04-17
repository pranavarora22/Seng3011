import { useEffect, useState } from "react";

export default function FilterBar({ filters, onApply }) {
  const [localFilters, setLocalFilters] = useState(filters);

  useEffect(() => {
    setLocalFilters(filters);
  }, [filters]);

  function handleChange(event) {
    const { name, value } = event.target;
    setLocalFilters((prev) => ({
      ...prev,
      [name]: name === "limit" ? Number(value) : value,
    }));
  }

  function handleSubmit(event) {
    event.preventDefault();
    onApply(localFilters);
  }

  return (
    <form className="panel filter-panel" onSubmit={handleSubmit}>
      <div className="panel-header">
        <h2>Filters</h2>
        <p>Choose the disease, country, and epidemiological week range.</p>
      </div>

      <div className="filter-grid">
        <label className="field">
          <span>Disease</span>
          <select
            name="disease"
            value={localFilters.disease}
            onChange={handleChange}
          >
            <option value="influenza">Influenza</option>
            <option value="rsv">RSV</option>
            <option value="sars-cov-2">SARS-CoV-2</option>
          </select>
        </label>

        <label className="field">
          <span>Country Code</span>
          <input
            type="text"
            name="country_code"
            value={localFilters.country_code}
            onChange={handleChange}
            placeholder="AUS"
          />
        </label>

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

      <div className="filter-actions">
        <button type="submit" className="primary-button">
          Apply Filters
        </button>
      </div>
    </form>
  );
}