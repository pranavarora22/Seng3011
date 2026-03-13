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

# ---------- Lambda ----------

resource "aws_lambda_function" "data_collector" {
  function_name    = "seng3011-data-collector"
  role             = data.aws_iam_role.lab_role.arn
  handler          = "lambda_function.lambda_handler"
  runtime          = "python3.10"
  timeout          = 60
  memory_size      = 256
  s3_bucket        = aws_s3_bucket.data_bucket.id
  s3_key           = aws_s3_object.lambda_code.key
  source_code_hash = filebase64sha256("deployment.zip")

  environment {
    variables = {
      S3_BUCKET  = aws_s3_bucket.data_bucket.id
      LOCAL_MOCK = "false"
    }
  }
}
