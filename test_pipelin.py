import json
from retrieval_lambda import lambda_handler
from disease_spike_detector import build_analytical_model

event = {"queryStringParameters": {"country_code": "PAK"}}

response = lambda_handler(event, None)

body = json.loads(response["body"])

if "items" not in body:
    print("Retrieval error:", body)
    exit()

records = body["items"]

signals = build_analytical_model(records)

print("records:", len(records))
print("signals:", len(signals))
print(signals[:3])