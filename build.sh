#!/usr/bin/env bash
# Build deployment.zip for AWS Lambda
# Always runs relative to the script's own directory, regardless of where it's called from.
set -euo pipefail

cd "$(dirname "$0")"

echo "Cleaning previous build..."
rm -rf .build_package
mkdir -p .build_package

echo "Installing dependencies..."
pip install -r requirements.txt -t .build_package --quiet

echo "Copying Lambda handlers and assets..."
cp lambda_function.py retrieval_lambda.py analytical_lambda.py openapi.yaml .build_package/

echo "Zipping..."
rm -f deployment.zip
cd .build_package && zip -r ../deployment.zip . -x "*.pyc" -x "__pycache__/*" > /dev/null

echo "Done: deployment.zip ($(du -sh ../deployment.zip | cut -f1))"
