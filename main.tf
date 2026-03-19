terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

provider "aws" {
  region = "us-east-1"
}

# ---------- Unique bucket name ----------

resource "random_id" "suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "data_bucket" {
  bucket = "seng3011-data-${random_id.suffix.hex}"
}

# ---------- IAM ----------
# Default: AWS Academy (uses pre-existing LabRole, cannot create IAM roles)
# Personal account: terraform apply -var="use_lab_role=false"

variable "use_lab_role" {
  description = "true = AWS Academy (uses pre-existing LabRole). false = personal account (creates IAM role)."
  type        = bool
  default     = true
}

data "aws_caller_identity" "current" {
  count = var.use_lab_role ? 1 : 0
}

resource "aws_iam_role" "lambda_role" {
  count = var.use_lab_role ? 0 : 1
  name  = "seng3011-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  count      = var.use_lab_role ? 0 : 1
  role       = aws_iam_role.lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy_attachment" "lambda_s3_dynamo" {
  count      = var.use_lab_role ? 0 : 1
  role       = aws_iam_role.lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonDynamoDBFullAccess"
}

resource "aws_iam_role_policy_attachment" "lambda_s3" {
  count      = var.use_lab_role ? 0 : 1
  role       = aws_iam_role.lambda_role[0].name
  policy_arn = "arn:aws:iam::aws:policy/AmazonS3FullAccess"
}

locals {
  lambda_role_arn = var.use_lab_role ? "arn:aws:iam::${data.aws_caller_identity.current[0].account_id}:role/LabRole" : aws_iam_role.lambda_role[0].arn
}

# ---------- Lambda code (S3 upload to avoid 50MB API limit) ----------

resource "aws_s3_object" "lambda_code" {
  bucket = aws_s3_bucket.data_bucket.id
  key    = "code/deployment.zip"
  source = "deployment.zip"
  etag   = filemd5("deployment.zip")
}

# ---------- DynamoDB table ----------

resource "aws_dynamodb_table" "disease_records" {
  name         = "seng3011-disease-records"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "epi_week"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "epi_week"
    type = "S"
  }

  attribute {
    name = "disease"
    type = "S"
  }

  # GSI 1: query all records for a disease (+ optional epi_week range)
  global_secondary_index {
    name            = "disease-week-index"
    hash_key        = "disease"
    range_key       = "epi_week"
    projection_type = "ALL"
  }
}

# ---------- Data collector Lambda ----------

resource "aws_lambda_function" "data_collector" {
  function_name    = "seng3011-data-collector"
  role             = local.lambda_role_arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.10"
  timeout          = 300 # full history fetch: influenza ~29 years, RSV ~10 years, COVID all rows
  memory_size      = 1024
  s3_bucket        = aws_s3_bucket.data_bucket.id
  s3_key           = aws_s3_object.lambda_code.key
  source_code_hash = filebase64sha256("deployment.zip")

  environment {
    variables = {
      S3_BUCKET    = aws_s3_bucket.data_bucket.id
      DYNAMO_TABLE = aws_dynamodb_table.disease_records.name
      LOCAL_MOCK   = "false"
    }
  }
}

# ---------- Retrieval Lambda ----------

resource "aws_lambda_function" "data_retriever" {
  function_name    = "seng3011-data-retriever"
  role             = local.lambda_role_arn
  handler          = "retrieval_lambda.lambda_handler"
  runtime          = "python3.10"
  timeout          = 30
  memory_size      = 256
  s3_bucket        = aws_s3_bucket.data_bucket.id
  s3_key           = aws_s3_object.lambda_code.key
  source_code_hash = filebase64sha256("deployment.zip")

  environment {
    variables = {
      S3_BUCKET    = aws_s3_bucket.data_bucket.id
      DYNAMO_TABLE = aws_dynamodb_table.disease_records.name
      LOCAL_MOCK   = "false"
    }
  }
}

# ---------- Retrieval API Gateway (HTTP API) ----------

resource "aws_apigatewayv2_api" "retriever_api" {
  name          = "seng3011-retriever-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "retriever_integration" {
  api_id                 = aws_apigatewayv2_api.retriever_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.data_retriever.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "retriever_route" {
  api_id    = aws_apigatewayv2_api.retriever_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.retriever_integration.id}"
}

resource "aws_apigatewayv2_stage" "retriever_stage" {
  api_id      = aws_apigatewayv2_api.retriever_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "retriever_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_retriever.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.retriever_api.execution_arn}/*/*"
}

# ---------- Analytical model Lambda ----------

resource "aws_lambda_function" "analytical_model" {
  function_name    = "seng3011-analytical-model"
  role             = local.lambda_role_arn
  handler          = "analytical_lambda.lambda_handler"
  runtime          = "python3.10"
  timeout          = 300
  memory_size      = 256
  s3_bucket        = aws_s3_bucket.data_bucket.id
  s3_key           = aws_s3_object.lambda_code.key
  source_code_hash = filebase64sha256("deployment.zip")

  environment {
    variables = {
      S3_BUCKET    = aws_s3_bucket.data_bucket.id
      DYNAMO_TABLE = aws_dynamodb_table.disease_records.name
      LOCAL_MOCK   = "false"
    }
  }
}

# ---------- Analytical API Gateway (HTTP API) ----------

resource "aws_apigatewayv2_api" "analytical_api" {
  name          = "seng3011-analytical-api"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "analytical_integration" {
  api_id                 = aws_apigatewayv2_api.analytical_api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.analytical_model.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "analytical_route" {
  api_id    = aws_apigatewayv2_api.analytical_api.id
  route_key = "$default"
  target    = "integrations/${aws_apigatewayv2_integration.analytical_integration.id}"
}

resource "aws_apigatewayv2_stage" "analytical_stage" {
  api_id      = aws_apigatewayv2_api.analytical_api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "analytical_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.analytical_model.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.analytical_api.execution_arn}/*/*"
}

# ---------- EventBridge weekly schedule ----------

resource "aws_cloudwatch_event_rule" "weekly_trigger" {
  name                = "seng3011-weekly-trigger"
  description         = "Trigger data collector Lambda every Monday at 00:00 UTC"
  schedule_expression = "cron(0 0 ? * MON *)"
}

resource "aws_cloudwatch_event_target" "lambda_target" {
  rule      = aws_cloudwatch_event_rule.weekly_trigger.name
  target_id = "seng3011DataCollector"
  arn       = aws_lambda_function.data_collector.arn
}

resource "aws_lambda_permission" "allow_eventbridge" {
  statement_id  = "AllowEventBridgeInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.data_collector.function_name
  principal     = "events.amazonaws.com"
  source_arn    = aws_cloudwatch_event_rule.weekly_trigger.arn
}

# ---------- Import blocks (Academy only – imports pre-existing resources into state) ----------
# These are only needed on AWS Academy where a prior hung apply may have created resources.
# On a fresh personal account, Terraform creates everything from scratch — imports are skipped.
# To activate: uncomment when re-deploying to Academy after a partial apply.

# import {
#   to = aws_dynamodb_table.disease_records
#   id = "seng3011-disease-records"
# }
# import {
#   to = aws_lambda_function.data_collector
#   id = "seng3011-data-collector"
# }
# import {
#   to = aws_lambda_function.data_retriever
#   id = "seng3011-data-retriever"
# }
# import {
#   to = aws_lambda_function.analytical_model
#   id = "seng3011-analytical-model"
# }
# import {
#   to = aws_lambda_function_url.retriever_url
#   id = "seng3011-data-retriever"
# }
# import {
#   to = aws_lambda_function_url.analytical_model_url
#   id = "seng3011-analytical-model"
# }
# import {
#   to = aws_lambda_permission.allow_eventbridge
#   id = "seng3011-data-collector/AllowEventBridgeInvoke"
# }

# ---------- Outputs ----------

output "bucket_name" {
  description = "S3 data bucket"
  value       = aws_s3_bucket.data_bucket.id
}

output "retrieval_function_url" {
  description = "Public HTTPS URL for the retrieval API"
  value       = aws_apigatewayv2_api.retriever_api.api_endpoint
}

output "analytical_model_function_url" {
  description = "Public HTTPS URL for the analytical model API"
  value       = aws_apigatewayv2_api.analytical_api.api_endpoint
}
