"""S3 integration tests for retrieval_lambda.py.

These tests run the retrieval handler locally, but the handler fetches its dataset
from AWS S3. Use this after the collection Lambda has uploaded
normalized-data/influenza_clean.json to your bucket.

Required environment variables before running:
    export S3_BUCKET=<your-terraform-created-bucket>
    export CLEAN_PREFIX=normalized-data
    unset LOCAL_MOCK
"""

import json
import os
import sys

# Ensure we do not accidentally force local mode.
os.environ.pop("LOCAL_MOCK", None)

from retrieval_lambda import lambda_handler



def require_env():
    """Fail fast if the bucket name has not been provided for the S3 test."""
    bucket = os.environ.get("S3_BUCKET")
    prefix = os.environ.get("CLEAN_PREFIX", "normalized-data")

    if not bucket:
        raise RuntimeError(
            "S3_BUCKET is not set. Example:\n"
            "  export S3_BUCKET=seng3011-data-xxxxxxxx\n"
            "  export CLEAN_PREFIX=normalized-data"
        )

    return bucket, prefix



def call(params):
    """Simulate an API Gateway request and return (status_code, body_dict)."""
    result = lambda_handler({"queryStringParameters": params}, None)
    return result["statusCode"], json.loads(result["body"])



def assert_true(condition, message):
    """Simple assertion helper."""
    if not condition:
        raise AssertionError(message)



def print_test_result(name, status, body):
    """Print a readable summary without flooding the terminal."""
    print(f"\n{name}")
    print(f"Status: {status}")
    print(json.dumps(body, indent=2)[:700])



def main():
    """Run integration tests against the real normalized dataset stored in S3."""
    bucket, prefix = require_env()
    print(f"Running S3 retrieval tests against s3://{bucket}/{prefix}/influenza_clean.json")

    # Basic retrieval should succeed if the object exists and contains rows.
    status, body = call({"disease": "influenza"})
    print_test_result("TEST 1: Basic influenza retrieval", status, body)
    assert_true(status in {200, 404}, f"Expected 200 or 404, got {status}: {body}")

    if status == 200:
        assert_true("count" in body and "items" in body, "Malformed success response")
        assert_true(
            all(item["payload"]["disease"] == "influenza" for item in body["items"]),
            "Non-influenza rows returned",
        )

    # Country filter can validly return either data or no results depending on dataset contents.
    status, body = call({"disease": "influenza", "country_code": "AUS"})
    print_test_result("TEST 2: Country filter", status, body)
    assert_true(status in {200, 404}, f"Expected 200 or 404, got {status}: {body}")
    if status == 200:
        assert_true(
            all(item["payload"]["country_code"] == "AUS" for item in body["items"]),
            "country_code filter failed",
        )

    # Epi-week range may or may not have matching rows, but it must never return rows outside the range.
    status, body = call({
        "disease": "influenza",
        "start_epi_week": "2025-W01",
        "end_epi_week": "2025-W10",
    })
    print_test_result("TEST 3: Epi-week range filter", status, body)
    assert_true(status in {200, 404}, f"Expected 200 or 404, got {status}: {body}")
    if status == 200:
        assert_true(
            all("2025-W01" <= item["payload"]["epi_week"] <= "2025-W10" for item in body["items"]),
            "epi_week range filter failed",
        )

    status, body = call({"disease": "influenza", "limit": "5"})
    print_test_result("TEST 4: Limit parameter", status, body)
    assert_true(status in {200, 404}, f"Expected 200 or 404, got {status}: {body}")
    if status == 200:
        assert_true(body["count"] <= 5, f"Expected at most 5 rows, got {body['count']}")
        assert_true(len(body["items"]) <= 5, f"Expected at most 5 items, got {len(body['items'])}")

    status, body = call({"disease": "covid"})
    print_test_result("TEST 5: Invalid disease", status, body)
    assert_true(status == 400, f"Expected 400 for invalid disease, got {status}: {body}")

    status, body = call({"disease": "influenza", "country_code": "AU"})
    print_test_result("TEST 6: Invalid country code", status, body)
    assert_true(status == 400, f"Expected 400 for invalid country code, got {status}: {body}")

    status, body = call({"disease": "influenza", "limit": "0"})
    print_test_result("TEST 7: Invalid limit", status, body)
    assert_true(status == 400, f"Expected 400 for invalid limit, got {status}: {body}")

    print("\nAll S3 retrieval tests passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\nTEST FAILED: {exc}")
        sys.exit(1)
