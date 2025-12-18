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
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
    }
  }
}

provider "aws" {
  region = "ca-central-1" # You can change this
}

variable "recaptcha_secret_key" {
  type        = string
  description = "The Secret Key for reCAPTCHA v3"
  sensitive   = true
}

variable "jira_domain" {
  type        = string
  description = "Jira Cloud Domain (e.g. your-site.atlassian.net)"
}

variable "jira_email" {
  type        = string
  description = "Email used for Jira Auth"
}

variable "jira_api_token" {
  type        = string
  description = "Jira API Token"
  sensitive   = true
}

variable "jira_project_key" {
  type        = string
  description = "Project Key for Jira Issues"
}

resource "random_id" "bucket_suffix" {
  byte_length = 8
}

# S3 Bucket for Logs
resource "aws_s3_bucket" "log_bucket" {
  bucket = "portfolio-logs-${random_id.bucket_suffix.hex}"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "portfolio_lambda_role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

# IAM Policy for Logging and S3 Access
resource "aws_iam_role_policy" "lambda_policy" {
  name = "portfolio_lambda_policy"
  role = aws_iam_role.lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject"
        ]
        Resource = "${aws_s3_bucket.log_bucket.arn}/*"
      }
    ]
  })
}

# Zip the Python code
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "aws_lambda_function.py"
  output_path = "lambda_function.zip"
}

# Lambda Function
resource "aws_lambda_function" "recaptcha_lambda" {
  filename         = "lambda_function.zip"
  function_name    = "portfolio_recaptcha_handler"
  role             = aws_iam_role.lambda_role.arn
  handler          = "aws_lambda_function.lambda_handler"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  runtime          = "python3.9"

  environment {
    variables = {
      RECAPTCHA_SECRET_KEY = var.recaptcha_secret_key
      LOG_BUCKET_NAME      = aws_s3_bucket.log_bucket.bucket
      JIRA_DOMAIN          = var.jira_domain
      JIRA_EMAIL           = var.jira_email
      JIRA_API_TOKEN       = var.jira_api_token
      JIRA_PROJECT_KEY     = var.jira_project_key
    }
  }
}

# Function URL
resource "aws_lambda_function_url" "lambda_url" {
  function_name      = aws_lambda_function.recaptcha_lambda.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = false
    allow_origins     = ["*"]
    allow_methods     = ["POST", "GET"]
    allow_headers     = ["date", "keep-alive", "content-type"]
    expose_headers    = ["keep-alive", "date"]
    max_age           = 86400
  }
}

# Required since Oct 2025: allow invoking the Function URL
resource "aws_lambda_permission" "function_url_allow_public_access" {
  statement_id          = "FunctionURLAllowPublicAccess"
  action                = "lambda:InvokeFunctionUrl"
  function_name         = aws_lambda_function.recaptcha_lambda.function_name
  principal             = "*"
  function_url_auth_type = "NONE"

  depends_on = [aws_lambda_function_url.lambda_url]
}

# Required since Oct 2025: also allow InvokeFunction
resource "aws_lambda_permission" "function_url_allow_invoke_function" {
  statement_id  = "FunctionURLInvokeAllowPublicAccess"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.recaptcha_lambda.function_name
  principal     = "*"

  depends_on = [aws_lambda_function_url.lambda_url]
}

output "function_url" {
  value = aws_lambda_function_url.lambda_url.function_url
}

output "log_bucket_name" {
  value = aws_s3_bucket.log_bucket.bucket
}
