export function downloadJsonFile(filename, data) {
  const blob = new Blob([JSON.stringify(data, null, 2)], {
    type: "application/json",
  });

  triggerDownload(blob, filename);
}

export function downloadCsvFile(filename, rows) {
  const csvContent = convertRowsToCsv(rows);
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });

  triggerDownload(blob, filename);
}

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");

  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);

  URL.revokeObjectURL(url);
}

function convertRowsToCsv(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return "country_code,epi_week,cases_detected,disease\n";
  }

  const headers = Object.keys(rows[0]);
  const headerLine = headers.join(",");

  const dataLines = rows.map((row) =>
    headers
      .map((header) => escapeCsvValue(row[header]))
      .join(",")
  );

  return [headerLine, ...dataLines].join("\n");
}

function escapeCsvValue(value) {
  if (value === null || value === undefined) {
    return "";
  }

  const stringValue = String(value);
  if (
    stringValue.includes(",") ||
    stringValue.includes('"') ||
    stringValue.includes("\n")
  ) {
    return `"${stringValue.replaceAll('"', '""')}"`;
  }

  return stringValue;
}