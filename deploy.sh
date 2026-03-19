#!/usr/bin/env bash
# Deploy infrastructure — works for both fresh and existing environments.
# Usage:
#   ./deploy.sh                  # AWS Academy (default)
#   ./deploy.sh --personal       # Personal AWS account
set -euo pipefail

cd "$(dirname "$0")"

# Build deployment zip
./build.sh

# Determine Terraform var
TF_ARGS=()
if [[ "${1:-}" == "--personal" ]]; then
  TF_ARGS=('-var=use_lab_role=false')
fi

terraform init -input=false

# Import pre-existing resources (silently skip if they don't exist or already in state)
terraform import "${TF_ARGS[@]}" aws_dynamodb_table.disease_records seng3011-disease-records 2>&1 | grep -v "already managed" || true
terraform import "${TF_ARGS[@]}" aws_lambda_function.data_collector seng3011-data-collector 2>&1 | grep -v "already managed" || true
terraform import "${TF_ARGS[@]}" aws_lambda_function.data_retriever seng3011-data-retriever 2>&1 | grep -v "already managed" || true
terraform import "${TF_ARGS[@]}" aws_lambda_function.analytical_model seng3011-analytical-model 2>&1 | grep -v "already managed" || true
terraform import "${TF_ARGS[@]}" aws_lambda_permission.allow_eventbridge seng3011-data-collector/AllowEventBridgeInvoke 2>&1 | grep -v "already managed" || true

terraform apply "${TF_ARGS[@]}"
