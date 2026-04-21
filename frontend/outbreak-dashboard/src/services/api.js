const RETRIEVAL_API =
  "https://4q6q6fbh4m.execute-api.ap-southeast-2.amazonaws.com";
const ANALYTICAL_API =
  "https://ikjc6t2sh5.execute-api.ap-southeast-2.amazonaws.com";
const MANGO_API_BASE =
  "https://x9rgu2z2vh.execute-api.us-east-1.amazonaws.com/prod/"; // ends with /

function buildQueryString(params) {
  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      searchParams.append(key, value);
    }
  });

  return searchParams.toString();
}

async function parseJsonResponse(response, fallbackLabel) {
  const text = await response.text();

  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }

  if (!response.ok) {
    const message =
      data?.error ||
      data?.message ||
      `${fallbackLabel} failed with status ${response.status}`;
    throw new Error(message);
  }

  return data;
}

export async function fetchDiseaseRecords({
  disease,
  country_code,
  start_epi_week,
  end_epi_week,
  limit = 100,
}) {
  const queryString = buildQueryString({
    disease,
    country_code,
    start_epi_week,
    end_epi_week,
    limit,
  });

  const response = await fetch(`${RETRIEVAL_API}?${queryString}`);
  return parseJsonResponse(response, "Retrieval API");
}

export async function fetchAnalyticalSignal({ disease, country_code }) {
  const queryString = buildQueryString({
    disease,
    country_code,
  });

  const response = await fetch(`${ANALYTICAL_API}?${queryString}`);
  return parseJsonResponse(response, "Analytical API");
}

export async function fetchUnemployment({ start, end }) {
  try {
    const queryString = buildQueryString({ start, end });

    const response = await fetch(
      `${MANGO_API_BASE}public/unemployment?${queryString}` // fixed (no extra /)
    );

    return await parseJsonResponse(response, "Unemployment API");
  } catch (error) {
    console.error("Unemployment API error:", error);
    return null;
  }
}

export async function fetchGDP({ start, end }) {
  try {
    const queryString = buildQueryString({ start, end });

    const response = await fetch(
      `${MANGO_API_BASE}public/gdp?${queryString}` // fixed (no extra /)
    );

    return await parseJsonResponse(response, "GDP API");
  } catch (error) {
    console.error("GDP API error:", error);
    return null;
  }
}

