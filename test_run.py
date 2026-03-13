"""Local test harness for the data collection Lambda function.

Sets LOCAL_MOCK=True so the handler reads from tests/mock_s3/raw-data/
and writes to tests/mock_s3/normalized-data/ using plain file I/O.
"""

import os
import json
import sys

def main():
    os.environ["LOCAL_MOCK"] = "True"

    out_dir = os.path.join("tests", "mock_s3", "normalized-data")
    os.makedirs(out_dir, exist_ok=True)

    from lambda_function import lambda_handler

    result = lambda_handler({}, None)
    print("\n=== Lambda Result ===")
    print(json.dumps(json.loads(result["body"]), indent=2))

    diseases = ["influenza", "salmonella", "meningococcal", "pneumococcal"]
    all_ok = True
    for disease in diseases:
        path = os.path.join(out_dir, f"{disease}_clean.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                records = json.load(f)
            print(f"  {disease}_clean.json: {len(records)} records, "
                  f"{os.path.getsize(path)} bytes")
        else:
            print(f"  WARNING: {path} not found!")
            all_ok = False

    if not all_ok:
        sys.exit(1)
    print("\nAll output files generated successfully.")


if __name__ == "__main__":
    main()
