"""Local test harness for the data collection Lambda.

Sets LOCAL_MOCK=True so the handler writes to tests/mock_s3/normalized-data/
without making any HTTP calls or touching AWS.
"""

import os
import json


def main():
    os.environ["LOCAL_MOCK"] = "True"

    out_dir = os.path.join("tests", "mock_s3", "normalized-data")
    os.makedirs(out_dir, exist_ok=True)

    from lambda_function import lambda_handler

    result = lambda_handler({}, None)
    print("\n=== Lambda Result ===")
    print(json.dumps(json.loads(result["body"]), indent=2))

    diseases = ["influenza", "rsv", "sars-cov-2"]
    for disease in diseases:
        path = os.path.join(out_dir, f"{disease}_clean.json")
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                records = json.load(f)
            print(f"  {disease}_clean.json: {len(records)} records, {os.path.getsize(path)} bytes")
        else:
            print(f"  {disease}_clean.json: no fixture — skipped in LOCAL_MOCK mode")

    print("\nDone.")


if __name__ == "__main__":
    main()
