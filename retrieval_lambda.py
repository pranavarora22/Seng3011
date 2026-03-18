import json
import logging
import os
from typing import Any, Dict, List
from urllib.parse import parse_qs

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

S3_BUCKET = os.environ.get("S3_BUCKET", "")
CLEAN_PREFIX = os.environ.get("CLEAN_PREFIX", "normalized-data")
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

VALID_DISEASES = {"influenza"}

s3 = boto3.client("s3")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def is_local_mock() -> bool:
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


def response(status_code: int, body: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_query_params(event: Dict[str, Any]) -> Dict[str, Any]:
    params = dict(event.get("queryStringParameters") or {})

    if not params and event.get("rawQueryString"):
        raw = parse_qs(event["rawQueryString"])
        params = {k: v[0] for k, v in raw.items() if v}

    disease = params.get("disease")
    country_code = params.get("country_code")
    start_epi_week = params.get("start_epi_week")
    end_epi_week = params.get("end_epi_week")
    limit = params.get("limit")

    if disease:
        disease = disease.strip().lower()
        if disease not in VALID_DISEASES:
            raise ValueError(
                f"Invalid disease '{disease}'. Expected one of: {sorted(VALID_DISEASES)}"
            )

    # ✅ FIXED HERE — supports both "AUS" and "Australia"
    COUNTRY_MAP = {
        "australia": "AUS",
        "india": "IND",
        "usa": "USA",
        "united states": "USA"
    }

    if country_code:
        country_code = country_code.strip()

        if len(country_code) == 3:
            country_code = country_code.upper()
        else:
            mapped = COUNTRY_MAP.get(country_code.lower())
            if not mapped:
                raise ValueError(
                    "Invalid country. Use 3-letter code (e.g. AUS) or supported name."
                )
            country_code = mapped

    for label, value in (("start_epi_week", start_epi_week), ("end_epi_week", end_epi_week)):
        if value:
            value = value.strip().upper()
            if len(value) != 8 or value[4:6] != "-W" or not value[:4].isdigit() or not value[6:].isdigit():
                raise ValueError(f"{label} must be in the format YYYY-W##, e.g. 2025-W04")
            week_num = int(value[6:])
            if week_num < 1 or week_num > 53:
                raise ValueError(f"{label} week must be between 01 and 53")
            if label == "start_epi_week":
                start_epi_week = value
            else:
                end_epi_week = value

    if start_epi_week and end_epi_week and start_epi_week > end_epi_week:
        raise ValueError("start_epi_week must be less than or equal to end_epi_week")

    if limit is not None:
        try:
            limit = int(limit)
        except ValueError as exc:
            raise ValueError("limit must be a positive integer") from exc
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

    return {
        "disease": disease,
        "country_code": country_code,
        "start_epi_week": start_epi_week,
        "end_epi_week": end_epi_week,
        "limit": limit,
    }


def load_records_for_disease(disease: str) -> List[Dict[str, Any]]:
    filename = f"{disease}_clean.json"

    if is_local_mock():
        path = os.path.join(LOCAL_CLEAN_PATH, filename)
        logger.info("Reading local normalized dataset from %s", path)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    if not S3_BUCKET:
        raise RuntimeError("S3_BUCKET environment variable is required when LOCAL_MOCK is false")

    key = f"{CLEAN_PREFIX}/{filename}"
    logger.info("Reading normalized dataset from s3://%s/%s", S3_BUCKET, key)

    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)
    return json.loads(obj["Body"].read().decode("utf-8"))


def record_matches(record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
    payload = record.get("payload", {})

    if filters["country_code"] and payload.get("country_code") != filters["country_code"]:
        return False

    epi_week = payload.get("epi_week")
    if epi_week is None:
        return False

    if filters["start_epi_week"] and epi_week < filters["start_epi_week"]:
        return False
    if filters["end_epi_week"] and epi_week > filters["end_epi_week"]:
        return False

    return True


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    try:
        filters = parse_query_params(event or {})
    except ValueError as exc:
        return response(400, {"error": str(exc)})

    diseases = [filters["disease"]] if filters["disease"] else sorted(VALID_DISEASES)

    try:
        matched: List[Dict[str, Any]] = []

        for disease in diseases:
            records = load_records_for_disease(disease)
            matched.extend([record for record in records if record_matches(record, filters)])

        matched.sort(
            key=lambda item: (
                item["payload"].get("epi_week", ""),
                item["payload"].get("country_code", ""),
                item["payload"].get("disease", ""),
            )
        )

        if filters["limit"] is not None:
            matched = matched[: filters["limit"]]

        if not matched:
            return response(404, {"error": "No records found for the supplied filters"})

        return response(
            200,
            {
                "count": len(matched),
                "filters": {k: v for k, v in filters.items() if v is not None},
                "items": matched,
            },
        )

    except FileNotFoundError as exc:
        logger.error("Missing local normalized file: %s", exc)
        return response(500, {"error": f"Normalized dataset missing: {exc}"})
    except s3.exceptions.NoSuchKey as exc:
        logger.error("Missing S3 object for retrieval: %s", exc)
        return response(500, {"error": "Normalized dataset is missing from S3"})
    except Exception as exc:
        logger.error("Retrieval failed: %s", exc, exc_info=True)
        return response(500, {"error": "Internal server error", "detail": str(exc)})