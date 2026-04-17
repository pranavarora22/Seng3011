export function formatNumber(value) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return numericValue.toLocaleString();
}

export function formatDecimal(value, digits = 2) {
  if (value === null || value === undefined || value === "") {
    return "N/A";
  }

  const numericValue = Number(value);
  if (Number.isNaN(numericValue)) {
    return String(value);
  }

  return numericValue.toFixed(digits);
}

export function getLatestRecord(records) {
  if (!Array.isArray(records) || records.length === 0) {
    return null;
  }

  return records[records.length - 1];
}

export function getRiskBadgeClass(riskLevel) {
  const value = String(riskLevel || "").toLowerCase();

  if (value.includes("critical") || value.includes("severe")) {
    return "badge badge-critical";
  }

  if (value.includes("high") || value.includes("emerging")) {
    return "badge badge-high";
  }

  if (value.includes("medium") || value.includes("elevated")) {
    return "badge badge-medium";
  }

  if (value.includes("low") || value.includes("normal")) {
    return "badge badge-low";
  }

  return "badge";
}