"""Local tests for retrieval_lambda.py.

These tests simulate API requests to the retrieval Lambda.

Important:
- They assume normalized JSON files already exist in:
  tests/mock_s3/normalized-data
- If those files do not exist yet, run `test_run.py` first
  to generate them from the raw CSV datasets.
"""

import json
import os
import sys

# Enable local testing mode.
# When LOCAL_MOCK=True, retrieval_lambda will read files from the
# local filesystem instead of trying to access AWS S3.
os.environ["LOCAL_MOCK"] = "True"

# Import the Lambda handler function we want to test
from retrieval_lambda import lambda_handler


def call(params):
    """
    Helper function to simulate an API Gateway request.

    It constructs a fake Lambda event containing query parameters,
    calls the Lambda handler, and returns the HTTP status code and body.
    """
    result = lambda_handler({"queryStringParameters": params}, None)
    body = json.loads(result["body"])
    return result["statusCode"], body


def assert_true(condition, message):
    """
    Simple assertion helper.

    If a condition fails, raise an error with a helpful message.
    This makes it easy to detect which test failed.
    """
    if not condition:
        raise AssertionError(message)


def main():
    """
    Runs a sequence of retrieval tests to verify that the
    filtering logic works correctly.
    """
    # Test 1: Disease + state filter
    # Expect influenza records from NSW only.
    status, body = call({
        "disease": "influenza",
        "state": "NSW"})
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] > 0, "Expected influenza NSW results")
    assert_true(all(item["payload"]["state"] == "NSW" for item in body["items"]), "State filter failed")

    # Test 2: Disease + date range filter
    # Ensure returned records fall inside the specified date window.
    status, body = call({
        "disease": "salmonella",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
    })
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(all("2025-01-01" <= item["payload"]["date"] <= "2025-01-31" for item in body["items"]), "Date filter failed")

    # Test 3: Invalid state
    # Passing an invalid state should trigger a 400 error.
    status, body = call({"disease": "meningococcal", "state": "ZZ"})
    assert_true(status == 400, f"Expected 400 for invalid state, got {status}")

    # Test 4: Limit parameter
    # Ensure the limit parameter correctly restricts the number of results.
    status, body = call({"disease": "pneumococcal", "limit": "5"})
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] == 5, f"Expected 5 rows, got {body['count']}")

    # Test 5: No matching records
    # If no records match the filters, the API should return 404.
    status, body = call({"disease": "influenza", "state": "TAS"})
    assert_true(status == 404, f"Expected 404 for no data, got {status}: {body}")

    # If all tests pass, print confirmation
    print("All retrieval tests passed.")


if __name__ == "__main__":
    """
    Entry point for running the tests from the command line.
    If any test fails, the script prints the error and exits with status 1.
    """
    try:
        main()
    except Exception as exc:
        print(f"TEST FAILED: {exc}")
        sys.exit(1)
