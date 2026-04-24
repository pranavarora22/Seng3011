const RETRIEVAL_API =
  import.meta.env.VITE_RETRIEVAL_API_URL ||
  "https://55uup6k9a6.execute-api.ap-southeast-2.amazonaws.com";
const ANALYTICAL_API =
  import.meta.env.VITE_ANALYTICAL_API_URL ||
  "https://9ug5j10r5c.execute-api.ap-southeast-2.amazonaws.com";

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

export async function fetchAnalyticalSignal({
  disease,
  country_code,
  start_epi_week,
  end_epi_week,
}) {
  const queryString = buildQueryString({
    disease,
    country_code,
    start_epi_week,
    end_epi_week,
  });

  const response = await fetch(`${ANALYTICAL_API}?${queryString}`);
  return parseJsonResponse(response, "Analytical API");
}
