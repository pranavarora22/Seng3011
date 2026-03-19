import os
import json
import logging
from datetime import datetime, timezone
from statistics import mean, pstdev

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "")
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "")
CLEAN_PREFIX = "normalized-data"
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

VALID_DISEASES = {"influenza", "rsv", "sars-cov-2"}

MIN_WEEKS_REQUIRED = 26  # ~6 months of weekly data for meaningful seasonal baseline


def compute_signals(records: list) -> list:
    from collections import defaultdict
    groups: dict = defaultdict(list)
    for rec in records:
        p = rec["payload"]
        groups[(p["disease"], p["country_code"])].append(p)

    signals = []
    for (disease, country_code), group in groups.items():
        group.sort(key=lambda x: tuple(int(p) for p in x["epi_week"].replace("-W", "-").split("-")))
        current = group[-1]

        if len(group) < MIN_WEEKS_REQUIRED:
            signals.append({
                "event_id": f"{disease}-{country_code}-{current['epi_week']}-signal",
                "event_type": "PUBLIC_HEALTH_SIGNAL",
                "domain": "HEALTH",
                "payload": {"risk_level": "INSUFFICIENT_DATA"},
            })
            continue

        history = group[:-1]
        current_week_num = int(current["epi_week"].split("-W")[1])
        same_week = [g["cases_detected"] for g in history if int(g["epi_week"].split("-W")[1]) == current_week_num]
        baseline = same_week if same_week else [g["cases_detected"] for g in history]
        s_mean = mean(baseline)

        current_cases = current["cases_detected"]
        s_std = pstdev(baseline)
        seasonal_z = (current_cases - s_mean) / s_std if s_std > 0 else 0.0
        seasonal_score = max(0, min(seasonal_z, 3)) / 3 * 100

        recent_avg = mean([g["cases_detected"] for g in history[-4:]]) if history else s_mean
        growth_rate = (current_cases - recent_avg) / max(recent_avg, 1)
        growth_score = max(0, min(growth_rate, 2)) / 2 * 100

        if len(history) >= 2:
            prev_cases = history[-1]["cases_detected"]
            prev_recent = [g["cases_detected"] for g in history[-5:-1]]
            prev_recent_avg = mean(prev_recent) if prev_recent else recent_avg
            prev_growth = (prev_cases - prev_recent_avg) / max(prev_recent_avg, 1)
            acceleration = growth_rate - prev_growth
        else:
            acceleration = 0.0
        accel_score = max(0, min(acceleration, 1)) * 100

        persistence_weeks = 0
        for g in reversed(group):
            if g["cases_detected"] > s_mean:
                persistence_weeks += 1
            else:
                break
        persistence_score = max(0, min(persistence_weeks, 8)) / 8 * 100

        risk_score = (
            0.40 * seasonal_score + 0.25 * growth_score
            + 0.20 * accel_score + 0.15 * persistence_score
        )

        # Declining: compute previous week's score
        prev_risk_score = None
        if len(history) >= MIN_WEEKS_REQUIRED:
            prev = history[-1]
            pw_num = int(prev["epi_week"].split("-W")[1])
            ph = history[:-1]
            pw = [g["cases_detected"] for g in ph if int(g["epi_week"].split("-W")[1]) == pw_num]
            pb = pw if pw else [g["cases_detected"] for g in ph]
            pm = mean(pb); ps = pstdev(pb)
            pz = (prev["cases_detected"] - pm) / ps if ps > 0 else 0.0
            pr_avg = mean([g["cases_detected"] for g in ph[-4:]]) if ph else pm
            pg = (prev["cases_detected"] - pr_avg) / max(pr_avg, 1)
            prev_risk_score = 0.40 * (max(0, min(pz, 3)) / 3 * 100) + 0.60 * (max(0, min(pg, 2)) / 2 * 100)

        risk_level = classify_risk_score(risk_score, prev_risk_score)

        signals.append({
            "event_id": f"{disease}-{country_code}-{current['epi_week']}-signal",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": "PUBLIC_HEALTH_SIGNAL",
            "domain": "HEALTH",
            "payload": {
                "disease": disease, "country_code": country_code,
                "epi_week": current["epi_week"], "current_cases": current_cases,
                "seasonal_mean": round(s_mean, 2), "seasonal_std_dev": round(s_std, 2),
                "seasonal_z_score": round(seasonal_z, 4), "growth_rate": round(growth_rate, 4),
                "acceleration": round(acceleration, 4), "persistence_weeks": persistence_weeks,
                "risk_score": round(risk_score, 2), "risk_level": risk_level,
            },
        })
    return signals


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


def classify_risk_score(score: float, prev_score: float | None = None) -> str:
    if prev_score is not None and prev_score >= 25 and score < prev_score - 20:
        return "Declining"
    if score < 25:
        return "Normal"
    if score < 50:
        return "Elevated"
    if score < 70:
        return "Emerging Outbreak"
    if score < 85:
        return "Sustained Outbreak"
    return "Severe Outbreak"




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
            signals = compute_signals(records)
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
