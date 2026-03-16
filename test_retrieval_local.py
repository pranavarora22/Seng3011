"""Local tests for retrieval_lambda.py.

These tests do not require AWS.
They create a small local fixture dataset under tests/mock_s3/normalized-data
and run the retrieval Lambda against it.
"""

import json
import os
import sys
from pathlib import Path

# Force retrieval_lambda to use local fixtures instead of S3.
os.environ["LOCAL_MOCK"] = "True"

from retrieval_lambda import lambda_handler


TEST_DATA = [
    {
        "event_id": "influenza-AUS-2025-W01",
        "timestamp": "2025-01-10T00:00:00+00:00",
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": "influenza",
            "country_code": "AUS",
            "epi_week": "2025-W01",
            "cases_detected": 10,
        },
    },
    {
        "event_id": "influenza-AUS-2025-W02",
        "timestamp": "2025-01-17T00:00:00+00:00",
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": "influenza",
            "country_code": "AUS",
            "epi_week": "2025-W02",
            "cases_detected": 14,
        },
    },
    {
        "event_id": "influenza-JPN-2025-W03",
        "timestamp": "2025-01-24T00:00:00+00:00",
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": "influenza",
            "country_code": "JPN",
            "epi_week": "2025-W03",
            "cases_detected": 22,
        },
    },
    {
        "event_id": "influenza-USA-2025-W04",
        "timestamp": "2025-01-31T00:00:00+00:00",
        "event_type": "PUBLIC_HEALTH_RECORD",
        "domain": "HEALTH",
        "payload": {
            "disease": "influenza",
            "country_code": "USA",
            "epi_week": "2025-W04",
            "cases_detected": 31,
        },
    },
]



def write_fixture_dataset() -> None:
    """Create a local normalized JSON file that retrieval_lambda will read."""
    folder = Path("tests/mock_s3/normalized-data")
    folder.mkdir(parents=True, exist_ok=True)

    target = folder / "influenza_clean.json"
    target.write_text(json.dumps(TEST_DATA, indent=2), encoding="utf-8")



def call(params):
    """Simulate an API Gateway request and return (status_code, body_dict)."""
    result = lambda_handler({"queryStringParameters": params}, None)
    return result["statusCode"], json.loads(result["body"])



def assert_true(condition, message):
    """Simple assertion helper with a readable message."""
    if not condition:
        raise AssertionError(message)



def main():
    """Run a compact set of local retrieval tests."""
    write_fixture_dataset()

    status, body = call({"disease": "influenza"})
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] == 4, f"Expected 4 rows, got {body['count']}")

    status, body = call({"disease": "influenza", "country_code": "AUS"})
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] == 2, f"Expected 2 AUS rows, got {body['count']}")
    assert_true(
        all(item["payload"]["country_code"] == "AUS" for item in body["items"]),
        "country_code filter failed",
    )

    status, body = call({
        "disease": "influenza",
        "start_epi_week": "2025-W02",
        "end_epi_week": "2025-W03",
    })
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] == 2, f"Expected 2 week-range rows, got {body['count']}")
    assert_true(
        all("2025-W02" <= item["payload"]["epi_week"] <= "2025-W03" for item in body["items"]),
        "epi_week range filter failed",
    )

    status, body = call({"disease": "influenza", "limit": "2"})
    assert_true(status == 200, f"Expected 200, got {status}: {body}")
    assert_true(body["count"] == 2, f"Expected 2 limited rows, got {body['count']}")

    status, body = call({"disease": "covid"})
    assert_true(status == 400, f"Expected 400 for invalid disease, got {status}: {body}")

    status, body = call({"disease": "influenza", "country_code": "AU"})
    assert_true(status == 400, f"Expected 400 for invalid country code, got {status}: {body}")

    status, body = call({"disease": "influenza", "country_code": "ZZZ"})
    assert_true(status == 404, f"Expected 404 for no results, got {status}: {body}")

    print("All local retrieval tests passed.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"TEST FAILED: {exc}")
        sys.exit(1)
