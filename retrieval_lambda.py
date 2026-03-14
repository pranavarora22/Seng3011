import os
import io
import json
import logging
from datetime import datetime
from urllib.parse import parse_qs

# Configure logger for Lambda execution logs
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables used when running in AWS
# S3_BUCKET: name of the S3 bucket storing normalized datasets
# CLEAN_PREFIX: folder/prefix inside the bucket where cleaned JSON files are stored
S3_BUCKET = os.environ.get("S3_BUCKET", "")
CLEAN_PREFIX = os.environ.get("CLEAN_PREFIX", "normalized-data")

# Local path used when running tests without AWS
LOCAL_CLEAN_PATH = os.path.join("tests", "mock_s3", "normalized-data")

# Allowed Australian states for validation
VALID_STATES = {"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"}

# Supported diseases in the system
VALID_DISEASES = {"influenza", "salmonella", "meningococcal", "pneumococcal"}


def is_local_mock():
    """
    Determines whether the function is running in local test mode.

    LOCAL_MOCK=true → use local files
    Otherwise → use AWS S3
    """
    return os.environ.get("LOCAL_MOCK", "").strip().lower() == "true"


def response(status_code, body):
    """
    Helper function to create a standardized Lambda HTTP response.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def parse_query_params(event):
    """
    Extracts and validates query parameters from the incoming request.

    Supported parameters:
    - disease
    - state
    - start_date
    - end_date
    - limit
    """

    # API Gateway usually provides queryStringParameters
    params = dict(event.get("queryStringParameters") or {})

    # Support rawQueryString shape used by Lambda Function URLs / HTTP API
    if not params and event.get("rawQueryString"):
        raw = parse_qs(event["rawQueryString"])
        params = {k: v[0] for k, v in raw.items() if v}

    disease = params.get("disease")
    state = params.get("state")
    start_date = params.get("start_date")
    end_date = params.get("end_date")
    limit = params.get("limit")

    # Validate disease parameter
    if disease:
        disease = disease.strip().lower()
        if disease not in VALID_DISEASES:
            raise ValueError(
                f"Invalid disease '{disease}'. Expected one of: {sorted(VALID_DISEASES)}"
            )

    # Validate state parameter
    if state:
        state = state.strip().upper()
        if state not in VALID_STATES:
            raise ValueError(
                f"Invalid state '{state}'. Expected one of: {sorted(VALID_STATES)}"
            )

    # Validate date parameters (must follow YYYY-MM-DD)
    for label, value in [("start_date", start_date), ("end_date", end_date)]:
        if value:
            datetime.strptime(value, "%Y-%m-%d")

    # Ensure date range is logical
    if start_date and end_date and start_date > end_date:
        raise ValueError("start_date must be less than or equal to end_date")

    # Validate limit parameter
    if limit is not None:
        limit = int(limit)
        if limit <= 0:
            raise ValueError("limit must be a positive integer")

    return {
        "disease": disease,
        "state": state,
        "start_date": start_date,
        "end_date": end_date,
        "limit": limit,
    }


def load_records_for_disease(disease):
    """
    Loads normalized JSON records for a specific disease.

    If running locally → read from local filesystem.
    If running in AWS → read from S3 bucket.
    """
    filename = f"{disease}_clean.json"

    # Local testing mode
    if is_local_mock():
        path = os.path.join(LOCAL_CLEAN_PATH, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    # AWS production mode
    import boto3
    s3 = boto3.client("s3")

    key = f"{CLEAN_PREFIX}/{filename}"
    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)

    return json.loads(obj["Body"].read().decode("utf-8"))


def record_matches(record, filters):
    """
    Checks whether a given record satisfies the requested filters.

    Filters applied:
    - state
    - start_date
    - end_date
    """

    payload = record.get("payload", {})

    # State filtering
    if filters["state"] and payload.get("state") != filters["state"]:
        return False

    # Date filtering
    record_date = payload.get("date")

    if filters["start_date"] and record_date < filters["start_date"]:
        return False
    if filters["end_date"] and record_date > filters["end_date"]:
        return False

    return True


def lambda_handler(event, context):
    """
    Main Lambda entry point.

    Workflow:
    1. Parse and validate query parameters
    2. Load normalized datasets
    3. Filter records
    4. Sort results
    5. Apply limit
    6. Return JSON response
    """

    # Step 1: Parse filters
    try:
        filters = parse_query_params(event or {})
    except ValueError as exc:
        return response(400, {"error": str(exc)})

    # Determine which diseases to search
    diseases = [filters["disease"]] if filters["disease"] else sorted(VALID_DISEASES)

    try:
        matched = []

        # Step 2–3: Load records and apply filters
        for disease in diseases:
            records = load_records_for_disease(disease)
            matched.extend([r for r in records if record_matches(r, filters)])

        # Step 4: Sort results by date → state → disease
        matched.sort(key=lambda r: (r["payload"]["date"], r["payload"]["state"], r["payload"]["disease"]))

        # Step 5: Apply result limit if specified
        if filters["limit"] is not None:
            matched = matched[: filters["limit"]]

        # If no matching records found
        if not matched:
            return response(404, {"error": "No records found for the supplied filters"})

        # Step 6: Return successful response
        return response(
            200,
            {
                "count": len(matched),
                "filters": {k: v for k, v in filters.items() if v is not None},
                "items": matched,
            },
        )

    # Error if normalized dataset file is missing
    except FileNotFoundError as exc:
        logger.error("Missing normalized file: %s", exc)
        return response(500, {"error": f"Normalized dataset missing: {exc}"})
    
    # Catch-all error handler
    except Exception as exc:
        logger.error("Retrieval failed: %s", exc, exc_info=True)
        return response(500, {"error": "Internal server error", "detail": str(exc)})
