import os
import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from statistics import mean, pstdev

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "")
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "")
CLEAN_PREFIX = "normalized-data"
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

VALID_DISEASES = {"influenza", "rsv", "sars-cov-2"}

# Minimum weeks of history required to compute a meaningful z-score
MIN_RECORDS_FOR_ZSCORE = 8


def is_local_mock() -> bool:
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


def load_records(disease: str) -> list:
    """Load all normalised records for a disease from DynamoDB or local fixture."""
    if is_local_mock():
        path = os.path.join(LOCAL_CLEAN_PATH, f"{disease}_clean.json")
        if not os.path.exists(path):
            logger.warning("%s: no local fixture at %s", disease, path)
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    import boto3
    from boto3.dynamodb.conditions import Key

    dynamo = boto3.resource("dynamodb")
    table = dynamo.Table(DYNAMO_TABLE)

    # Paginate through all records for this disease via GSI 1
    items = []
    last_key = None
    while True:
        kwargs = {
            "IndexName": "disease-week-index",
            "KeyConditionExpression": Key("disease").eq(disease),
        }
        if last_key:
            kwargs["ExclusiveStartKey"] = last_key
        resp = table.query(**kwargs)
        items.extend(resp.get("Items", []))
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break

    return [
        {
            "event_id": item.get("event_id", ""),
            "timestamp": item.get("timestamp", ""),
            "event_type": "PUBLIC_HEALTH_RECORD",
            "domain": "HEALTH",
            "payload": {
                "disease": item["disease"],
                "country_code": item["country_code"],
                "epi_week": item["epi_week"],
                "cases_detected": int(item.get("cases_detected", 0)),
            },
        }
        for item in items
    ]


def classify_z_score(z: float) -> str:
    if z < 1.0:
        return "LOW"
    if z < 2.0:
        return "MEDIUM"
    if z < 3.0:
        return "HIGH"
    return "CRITICAL"


def build_signal_record(
    disease: str,
    country_code: str,
    epi_week: str,
    current_cases: int,
    hist_mean: float,
    hist_std: float,
    z_score: float | None,
    risk_level: str,
    timestamp: str,
) -> dict:
    return {
        "event_id": f"{disease}-{country_code}-{epi_week}-signal",
        "timestamp": timestamp,
        "event_type": "PUBLIC_HEALTH_SIGNAL",
        "domain": "HEALTH",
        "payload": {
            "disease": disease,
            "country_code": country_code,
            "epi_week": epi_week,
            "current_cases": current_cases,
            "historical_mean": round(hist_mean, 2),
            "historical_std_dev": round(hist_std, 2),
            "z_score": round(z_score, 4) if z_score is not None else None,
            "risk_level": risk_level,
        },
    }


def compute_z_scores(records: list) -> list:
    """Compute z-score risk signals from normalised disease records.

    Groups by (disease, country_code), uses the full history as the baseline,
    and scores the most recent epi_week per group.

    Uses population std dev (pstdev) because the stored records represent the
    complete population of observed weeks, not a sample.
    """
    timestamp = datetime.now(timezone.utc).isoformat()

    groups: dict[tuple, list] = defaultdict(list)
    for rec in records:
        p = rec["payload"]
        groups[(p["disease"], p["country_code"])].append(p)

    signals = []
    for (disease, country_code), group in groups.items():
        group.sort(key=lambda x: x["epi_week"])
        case_counts = [g["cases_detected"] for g in group]
        current = group[-1]

        if len(group) < MIN_RECORDS_FOR_ZSCORE:
            signals.append(
                build_signal_record(
                    disease, country_code, current["epi_week"],
                    current["cases_detected"], 0.0, 0.0, None,
                    "INSUFFICIENT_DATA", timestamp,
                )
            )
            continue

        hist_mean = mean(case_counts)
        hist_std = pstdev(case_counts)

        if hist_std == 0:
            signals.append(
                build_signal_record(
                    disease, country_code, current["epi_week"],
                    current["cases_detected"], hist_mean, 0.0, 0.0,
                    "STABLE", timestamp,
                )
            )
            continue

        z = (current["cases_detected"] - hist_mean) / hist_std
        signals.append(
            build_signal_record(
                disease, country_code, current["epi_week"],
                current["cases_detected"], hist_mean, hist_std, z,
                classify_z_score(z), timestamp,
            )
        )

    return signals


def parse_query_params(event: dict) -> dict:
    params = event.get("queryStringParameters") or {}
    return {
        "disease": params.get("disease", "").lower() or None,
        "country_code": params.get("country_code", "").upper() or None,
        "start_epi_week": params.get("start_epi_week") or None,
        "end_epi_week": params.get("end_epi_week") or None,
        "limit": min(int(params.get("limit", 100)), 1000),
    }


_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Disease Surveillance — Analytical API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
const spec = {spec_json};
SwaggerUIBundle({{
  spec: spec,
  dom_id: '#swagger-ui',
  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
  layout: 'BaseLayout'
}});
</script>
</body>
</html>"""


def _docs_response() -> dict:
    """Return Swagger UI HTML for the Analytical API."""
    import json as _json
    import os as _os

    spec_path = _os.path.join(_os.path.dirname(__file__), "openapi.yaml")
    try:
        import yaml  # type: ignore

        with open(spec_path, encoding="utf-8") as f:
            spec = _json.loads(_json.dumps(yaml.safe_load(f)))  # normalise to plain dict
    except Exception:
        spec = {"openapi": "3.0.3", "info": {"title": "Analytical API", "version": "1.0.0"}, "paths": {}}

    html = _SWAGGER_UI_HTML.replace("{spec_json}", _json.dumps(spec))
    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}


def lambda_handler(event, context):
    """Return z-score risk signals for filtered diseases/countries."""
    if event.get("rawPath") == "/docs":
        return _docs_response()

    filters = parse_query_params(event)
    logger.info("Analytical query: %s", filters)

    diseases = [filters["disease"]] if filters["disease"] else list(VALID_DISEASES)
    all_signals = []

    for disease in diseases:
        try:
            records = load_records(disease)
            if not records:
                all_signals.append({"disease": disease, "error": "data unavailable"})
                continue
            signals = compute_z_scores(records)
        except Exception as e:
            logger.error("%s: analytical failed — %s", disease, e, exc_info=True)
            all_signals.append({"disease": disease, "error": str(e)})
            continue

        if filters["country_code"]:
            signals = [
                s for s in signals
                if s.get("payload", {}).get("country_code") == filters["country_code"]
            ]
        if filters["start_epi_week"]:
            signals = [
                s for s in signals
                if s.get("payload", {}).get("epi_week", "") >= filters["start_epi_week"]
            ]
        if filters["end_epi_week"]:
            signals = [
                s for s in signals
                if s.get("payload", {}).get("epi_week", "") <= filters["end_epi_week"]
            ]

        all_signals.extend(signals[: filters["limit"]])

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps({"count": len(all_signals), "signals": all_signals}),
    }
