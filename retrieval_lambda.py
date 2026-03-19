import os
import json
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ.get("S3_BUCKET", "")
DYNAMO_TABLE = os.environ.get("DYNAMO_TABLE", "")
CLEAN_PREFIX = "normalized-data"
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

VALID_DISEASES = {"influenza", "rsv", "sars-cov-2"}

# Common country name aliases → ISO 3166-1 alpha-3
COUNTRY_MAP = {
    "australia": "AUS",
    "india": "IND",
    "usa": "USA",
    "united states": "USA",
    "united states of america": "USA",
    "uk": "GBR",
    "united kingdom": "GBR",
    "china": "CHN",
    "france": "FRA",
    "germany": "DEU",
    "brazil": "BRA",
    "canada": "CAN",
    "japan": "JPN",
    "south africa": "ZAF",
    "nigeria": "NGA",
    "indonesia": "IDN",
    "pakistan": "PAK",
    "mexico": "MEX",
    "new zealand": "NZL",
}


def is_local_mock() -> bool:
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


def resolve_country(raw: str) -> str:
    """Normalise a country input to a 3-letter ISO code."""
    upper = raw.strip().upper()
    if len(upper) == 3 and upper.isalpha():
        return upper
    return COUNTRY_MAP.get(raw.strip().lower(), upper)


def parse_query_params(event: dict) -> dict:
    params = event.get("queryStringParameters") or {}
    disease = params.get("disease", "").lower() or None
    country_raw = params.get("country_code", "")
    country_code = resolve_country(country_raw) if country_raw else None
    return {
        "disease": disease,
        "country_code": country_code,
        "start_epi_week": params.get("start_epi_week") or None,
        "end_epi_week": params.get("end_epi_week") or None,
        "limit": min(int(params.get("limit", 100)), 1000),
    }


def query_dynamo(filters: dict) -> list:
    """Query DynamoDB using the most appropriate key/index for the given filters."""
    import boto3
    from boto3.dynamodb.conditions import Key, Attr

    dynamo = boto3.resource("dynamodb")
    table = dynamo.Table(DYNAMO_TABLE)

    disease = filters["disease"]
    country_code = filters["country_code"]
    start_week = filters["start_epi_week"]
    end_week = filters["end_epi_week"]
    limit = filters["limit"]

    # Build optional week range condition on the sort key
    week_condition = None
    if start_week and end_week:
        week_condition = Key("epi_week").between(start_week, end_week)
    elif start_week:
        week_condition = Key("epi_week").gte(start_week)
    elif end_week:
        week_condition = Key("epi_week").lte(end_week)

    if disease and country_code:
        # Main table: PK = disease#country_code, SK = epi_week
        pk_cond = Key("pk").eq(f"{disease}#{country_code}")
        key_cond = (pk_cond & week_condition) if week_condition else pk_cond
        resp = table.query(KeyConditionExpression=key_cond, Limit=limit)

    elif disease:
        # GSI 1 (disease-week-index): PK = disease, SK = epi_week
        pk_cond = Key("disease").eq(disease)
        key_cond = (pk_cond & week_condition) if week_condition else pk_cond
        resp = table.query(
            IndexName="disease-week-index",
            KeyConditionExpression=key_cond,
            Limit=limit,
        )

    else:
        # No disease filter — scan with optional week filter expression
        filter_expr = None
        if start_week and end_week:
            filter_expr = Attr("epi_week").between(start_week, end_week)
        elif start_week:
            filter_expr = Attr("epi_week").gte(start_week)
        elif end_week:
            filter_expr = Attr("epi_week").lte(end_week)
        kwargs = {"Limit": limit}
        if filter_expr:
            kwargs["FilterExpression"] = filter_expr
        resp = table.scan(**kwargs)

    return resp.get("Items", [])


def format_items(items: list) -> list:
    """Convert DynamoDB items back to PUBLIC_HEALTH_RECORD schema."""
    return [
        {
            "event_id": item.get("event_id", ""),
            "timestamp": item.get("timestamp", ""),
            "event_type": "PUBLIC_HEALTH_RECORD",
            "domain": "HEALTH",
            "payload": {
                "disease": item.get("disease", ""),
                "country_code": item.get("country_code", ""),
                "epi_week": item.get("epi_week", ""),
                "cases_detected": int(item.get("cases_detected", 0)),
            },
        }
        for item in items
    ]


def load_records_from_s3(disease: str) -> list:
    """Load full disease file from local fixture (LOCAL_MOCK) or S3."""
    if is_local_mock():
        path = os.path.join(LOCAL_CLEAN_PATH, f"{disease}_clean.json")
        if not os.path.exists(path):
            return []
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    import boto3

    s3 = boto3.client("s3")
    key = f"{CLEAN_PREFIX}/{disease}_clean.json"
    try:
        resp = s3.get_object(Bucket=S3_BUCKET, Key=key)
        return json.loads(resp["Body"].read())
    except Exception:
        return []


_SWAGGER_UI_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>Disease Surveillance — Retrieval API</title>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <link rel="stylesheet" href="https://unpkg.com/swagger-ui-dist@5/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
const spec = {spec_json};
SwaggerUIBundle({
  spec: spec,
  dom_id: '#swagger-ui',
  presets: [SwaggerUIBundle.presets.apis, SwaggerUIBundle.SwaggerUIStandalonePreset],
  layout: 'BaseLayout'
});
</script>
</body>
</html>"""


def _docs_response() -> dict:
    """Return Swagger UI HTML for the Retrieval API."""
    import json as _json
    import os as _os

    spec_path = _os.path.join(_os.path.dirname(__file__), "openapi.yaml")
    try:
        import yaml  # type: ignore

        with open(spec_path, encoding="utf-8") as f:
            spec = yaml.safe_load(f)
    except Exception:
        spec = {"openapi": "3.0.3", "info": {"title": "Retrieval API", "version": "1.0.0"}, "paths": {}}

    html = _SWAGGER_UI_HTML.replace("{spec_json}", _json.dumps(spec))
    return {"statusCode": 200, "headers": {"Content-Type": "text/html"}, "body": html}


def lambda_handler(event, context):
    """Retrieve filtered disease records from DynamoDB (or S3 in local mock mode)."""
    if event.get("rawPath") == "/docs":
        return _docs_response()

    filters = parse_query_params(event)
    logger.info("Query filters: %s", filters)

    try:
        if is_local_mock():
            disease = filters["disease"] or "influenza"
            raw = load_records_from_s3(disease)
            items = [
                r
                for r in raw
                if (
                    not filters["country_code"]
                    or r.get("payload", {}).get("country_code") == filters["country_code"]
                )
                and (
                    not filters["start_epi_week"]
                    or r.get("payload", {}).get("epi_week", "") >= filters["start_epi_week"]
                )
                and (
                    not filters["end_epi_week"]
                    or r.get("payload", {}).get("epi_week", "") <= filters["end_epi_week"]
                )
            ][: filters["limit"]]
        else:
            raw_items = query_dynamo(filters)
            items = format_items(raw_items)

        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"count": len(items), "items": items}),
        }
    except Exception as e:
        logger.error("Retrieval failed: %s", e, exc_info=True)
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"error": str(e)}),
        }
