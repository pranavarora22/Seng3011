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

# ---------- IAM (AWS Academy – use existing LabRole) ----------

data "aws_iam_role" "lab_role" {
  name = "LabRole"
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
  role             = data.aws_iam_role.lab_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.10"
  timeout          = 300 # full history fetch: influenza ~29 years, RSV ~10 years, COVID all rows
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

# ---------- Retrieval Lambda ----------

resource "aws_lambda_function" "data_retriever" {
  function_name    = "seng3011-data-retriever"
  role             = data.aws_iam_role.lab_role.arn
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

resource "aws_lambda_function_url" "retriever_url" {
  function_name      = aws_lambda_function.data_retriever.function_name
  authorization_type = "NONE"
}

# ---------- Analytical model Lambda ----------

resource "aws_lambda_function" "analytical_model" {
  function_name    = "seng3011-analytical-model"
  role             = data.aws_iam_role.lab_role.arn
  handler          = "analytical_lambda.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
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

resource "aws_lambda_function_url" "analytical_model_url" {
  function_name      = aws_lambda_function.analytical_model.function_name
  authorization_type = "NONE"
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

# ---------- Outputs ----------

output "bucket_name" {
  description = "S3 data bucket"
  value       = aws_s3_bucket.data_bucket.id
}

output "retrieval_function_url" {
  description = "Public HTTPS URL for the retrieval Lambda"
  value       = aws_lambda_function_url.retriever_url.function_url
}

output "analytical_model_function_url" {
  description = "Public HTTPS URL for the analytical model Lambda"
  value       = aws_lambda_function_url.analytical_model_url.function_url
}
