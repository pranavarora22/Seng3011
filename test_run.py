
"""Local test harness for the data collection Lambda function.

Sets LOCAL_MOCK=True so the handler writes to tests/mock_s3/normalized-data/.
In mock mode, process_flunet_disease skips real HTTP calls and returns [].
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

    path = os.path.join(out_dir, "influenza_clean.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            records = json.load(f)
        print(f"  influenza_clean.json: {len(records)} records, {os.path.getsize(path)} bytes")
    else:
        print(f"  WARNING: {path} not found!")
        sys.exit(1)

    print("\nOutput file generated successfully.")


if __name__ == "__main__":
    main()
