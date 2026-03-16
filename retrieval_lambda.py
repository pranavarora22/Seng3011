import os
import json
import logging
import boto3
from urllib.parse import parse_qs

# Configure logger so errors and runtime information appear in AWS CloudWatch
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Environment variables used to locate normalized datasets in S3
# S3_BUCKET: bucket storing cleaned datasets
# CLEAN_PREFIX: folder inside the bucket containing JSON files
S3_BUCKET = os.environ["S3_BUCKET"]
CLEAN_PREFIX = os.environ.get("CLEAN_PREFIX", "normalized-data")

# Currently the service only supports influenza data
VALID_DISEASES = {"influenza"}

# Create an S3 client for retrieving files
s3 = boto3.client("s3")


def response(status_code, body):
    """
    Helper function to construct a standard HTTP response
    returned by the Lambda function.
    """
    return {
        "statusCode": status_code,
        "headers": {"Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def parse_query_params(event):
    """
    Extract and validate query parameters from an API request.

    Supported parameters:
        disease
        country_code
        start_epi_week
        end_epi_week
        limit
    """

    # API Gateway typically provides queryStringParameters
    params = dict(event.get("queryStringParameters") or {})

    # Lambda Function URLs sometimes send rawQueryString instead
    if not params and event.get("rawQueryString"):
        raw = parse_qs(event["rawQueryString"])
        params = {k: v[0] for k, v in raw.items() if v}

    disease = params.get("disease")
    country_code = params.get("country_code")
    start_epi_week = params.get("start_epi_week")
    end_epi_week = params.get("end_epi_week")
    limit = params.get("limit")

    # Validate disease
    if disease:
        disease = disease.lower()
        if disease not in VALID_DISEASES:
            raise ValueError(f"Invalid disease '{disease}'")

    # Validate country code
    if country_code:
        country_code = country_code.upper()
        if len(country_code) != 3:
            raise ValueError("country_code must be a 3-letter code")

    # Validate limit
    if limit is not None:
        limit = int(limit)
        if limit <= 0:
            raise ValueError("limit must be positive")

    return {
        "disease": disease,
        "country_code": country_code,
        "start_epi_week": start_epi_week,
        "end_epi_week": end_epi_week,
        "limit": limit,
    }


def load_records_from_s3(disease):
    """
    Load normalized dataset from S3.

    Each disease has its own normalized JSON file
    produced by the data collection Lambda.
    """

    filename = f"{disease}_clean.json"
    key = f"{CLEAN_PREFIX}/{filename}"

    logger.info(f"Reading dataset from S3: {key}")

    obj = s3.get_object(Bucket=S3_BUCKET, Key=key)

    return json.loads(obj["Body"].read().decode("utf-8"))


def record_matches(record, filters):
    """
    Determine whether a record matches the supplied filters.
    """

    payload = record["payload"]

    # Filter by country
    if filters["country_code"]:
        if payload["country_code"] != filters["country_code"]:
            return False

    epi_week = payload["epi_week"]

    # Filter by epi week range
    if filters["start_epi_week"] and epi_week < filters["start_epi_week"]:
        return False

    if filters["end_epi_week"] and epi_week > filters["end_epi_week"]:
        return False

    return True


def lambda_handler(event, context):
    """
    Main Lambda entry point.

    Workflow:
        1. Parse query parameters
        2. Load dataset from S3
        3. Apply filters
        4. Sort results
        5. Apply limit
        6. Return JSON response
    """

    # Step 1: parse filters
    try:
        filters = parse_query_params(event)
    except ValueError as e:
        return response(400, {"error": str(e)})

    disease = filters["disease"] or "influenza"

    try:
        # Step 2: load dataset from S3
        records = load_records_from_s3(disease)

        # Step 3: apply filtering
        matched = [r for r in records if record_matches(r, filters)]

        # Step 4: sort results for consistent ordering
        matched.sort(
            key=lambda r: (
                r["payload"]["epi_week"],
                r["payload"]["country_code"]
            )
        )

        # Step 5: apply limit if requested
        if filters["limit"]:
            matched = matched[: filters["limit"]]

        # If no records match
        if not matched:
            return response(404, {"error": "No records found"})

        # Step 6: return response
        return response(
            200,
            {
                "count": len(matched),
                "items": matched,
            },
        )

    except Exception as e:
        logger.error(e, exc_info=True)
        return response(500, {"error": "Internal server error"})
        