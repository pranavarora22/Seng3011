import json
import os
from retrieval_lambda import lambda_handler

# Configure environment variables so the retrieval Lambda
# knows which S3 bucket to read datasets from.
os.environ["S3_BUCKET"] = ""
os.environ["CLEAN_PREFIX"] = "normalized-data"


def call(params):
    """
    Simulate an API Gateway request to the Lambda function.

    Returns the HTTP status code and parsed JSON body.
    """
    result = lambda_handler({"queryStringParameters": params}, None)
    body = json.loads(result["body"])
    return result["statusCode"], body


def assert_true(cond, msg):
    """
    Simple assertion helper used by tests.
    Raises an error if a condition fails.
    """
    if not cond:
        raise AssertionError(msg)


def main():

    # Test 1: Basic retrieval
    # Ensure influenza data can be loaded successfully from S3
    status, body = call({"disease": "influenza"})
    assert_true(status == 200, f"Expected 200 got {status}")

    # Test 2: Country filter
    # Verify that country filtering works correctly
    status, body = call({"disease": "influenza", "country_code": "AUS"})
    if status == 200:
        assert_true(
            all(i["payload"]["country_code"] == "AUS" for i in body["items"]),
            "Country filter failed",
        )

    # Test 3: Epidemiological week range
    # Check that records fall within the specified epi-week window
    status, body = call({
        "disease": "influenza",
        "start_epi_week": "2024-W01",
        "end_epi_week": "2024-W10"
    })

    if status == 200:
        assert_true(
            all("2024-W01" <= i["payload"]["epi_week"] <= "2024-W10"
                for i in body["items"]),
            "Epi week filter failed"
        )

    # Test 4: Limit parameter
    # Ensure that the result size respects the limit parameter
    status, body = call({"disease": "influenza", "limit": "5"})
    if status == 200:
        assert_true(body["count"] <= 5, "Limit failed")

    print("All S3 retrieval tests passed.")


if __name__ == "__main__":
    main()