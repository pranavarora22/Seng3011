import json
from retrieval_lambda import lambda_handler

# Simulate API Gateway event
event = {
    "queryStringParameters": {
        "country_code": "AUS",   # change this to test different countries
        "disease": "influenza"
    }
}

# Call your lambda
response = lambda_handler(event, None)

# Pretty print full response
print("STATUS:", response["statusCode"])

body = json.loads(response["body"])

print("COUNT:", body["count"])
print("FILTERS:", body["filters"])

# Print first 3 items only (clean output)
print("\nSample data:")
for item in body["items"][:3]:
    print(item)