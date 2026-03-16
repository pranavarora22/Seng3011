import os
import json
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

FLUNET_API = "https://xmart-api-public.who.int/FLUMART/VIW_FNT"
FLUNET_LOOKBACK_YEARS = 2


def fetch_flunet_records(year):
    """Fetch all FluNet records for a given year from the WHO OData API (all countries)."""
    url = f"{FLUNET_API}?$filter=ISO_YEAR eq {year}"
    response = requests.get(url, timeout=30)
    response.raise_for_status()
    return response.json().get("value", [])


S3_BUCKET = os.environ.get("S3_BUCKET", "")
RAW_PREFIX = "raw-data"
CLEAN_PREFIX = "normalized-data"
LOCAL_RAW_PATH = os.path.join("tests", "mock_s3", "raw-data")
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_local_mock():
    """Check if we should use local file I/O instead of S3."""
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"



def process_flunet_disease():
    """Fetch WHO FluNet data and build normalized records."""
    if is_local_mock():
        fixture = os.path.join(LOCAL_RAW_PATH, "influenza_who.json")
        if os.path.exists(fixture):
            with open(fixture, encoding="utf-8") as f:
                return json.load(f)
        logger.warning("process_flunet_disease: LOCAL_MOCK mode, no fixture found — returning []")
        return []
    timestamp = datetime.now(timezone.utc).isoformat()
    current_year = datetime.now(timezone.utc).year
    raw = []
    for year in range(current_year - FLUNET_LOOKBACK_YEARS + 1, current_year + 1):
        raw.extend(fetch_flunet_records(year))
    records = []
    for r in raw:
        if not r.get("INF_ALL"):
            continue
        epi_week = f"{r['ISO_YEAR']}-W{int(r['ISO_WEEK']):02d}"
        records.append({
            "event_id": f"influenza-{r['COUNTRY_CODE']}-{epi_week}",
            "timestamp": timestamp,
            "event_type": "PUBLIC_HEALTH_RECORD",
            "domain": "HEALTH",
            "payload": {
                "disease": "influenza",
                "country_code": r["COUNTRY_CODE"],
                "epi_week": epi_week,
                "cases_detected": int(r["INF_ALL"]),
            },
        })
    return records

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def save_output(disease_name, records):
    """Write normalized JSON records to local disk or S3."""
    filename = f"{disease_name}_clean.json"
    data = json.dumps(records, indent=2)

    if is_local_mock():
        os.makedirs(LOCAL_CLEAN_PATH, exist_ok=True)
        path = os.path.join(LOCAL_CLEAN_PATH, filename)
        with open(path, "w", encoding="utf-8") as f:
            f.write(data)
        logger.info("Saved %s (%d records) to %s", filename, len(records), path)
    else:
        import boto3
        s3 = boto3.client("s3")
        key = f"{CLEAN_PREFIX}/{filename}"
        s3.put_object(Bucket=S3_BUCKET, Key=key, Body=data,
                      ContentType="application/json")
        logger.info("Uploaded %s (%d records) to s3://%s/%s",
                    filename, len(records), S3_BUCKET, key)

# ---------------------------------------------------------------------------
# Lambda handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """Main Lambda entry point."""
    logger.info("Starting data collection pipeline")
    results = {}

    try:
        records = process_flunet_disease()
        save_output("influenza", records)
        results["influenza"] = {"status": "success", "records": len(records)}
        logger.info("influenza: processed %d records", len(records))
    except Exception as e:
        logger.error("influenza (WHO): failed — %s", e, exc_info=True)
        results["influenza"] = {"status": "error", "message": str(e)}

    logger.info("Pipeline complete: %s", results)
    return {"statusCode": 200, "body": json.dumps(results)}
