provider "aws" {
  region = "ca-central-1" # You can change this
}

variable "recaptcha_secret_key" {
  type        = string
  description = "The Secret Key for reCAPTCHA v3"
  sensitive   = true
}

resource "random_id" "bucket_suffix" {
  byte_length = 8
}

# S3 Bucket for Logs
resource "aws_s3_bucket" "log_bucket" {
  bucket = "portfolio-recaptcha-logs-${random_id.bucket_suffix.hex}"
}

# IAM Role for Lambda
resource "aws_iam_role" "lambda_role" {
  name = "portfolio_recaptcha_lambda_role"

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
  name = "portfolio_recaptcha_lambda_policy"
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
    }
  }
}

# Function URL
resource "aws_lambda_function_url" "lambda_url" {
  function_name      = aws_lambda_function.recaptcha_lambda.function_name
  authorization_type = "NONE"

  cors {
    allow_credentials = true
    allow_origins     = ["*"]
    allow_methods     = ["POST", "OPTIONS"]
    allow_headers     = ["date", "keep-alive", "content-type"]
    expose_headers    = ["keep-alive", "date"]
    max_age           = 86400
  }
}

output "function_url" {
  value = aws_lambda_function_url.lambda_url.function_url
}

output "log_bucket_name" {
  value = aws_s3_bucket.log_bucket.bucket
}
