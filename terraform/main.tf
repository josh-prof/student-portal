terraform {
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.0" }
  }
}

provider "aws" {
  region = var.region
}

# Billing metrics only exist in us-east-1
provider "aws" {
  alias  = "virginia"
  region = "us-east-1"
}

data "aws_caller_identity" "me" {}

############ MODULE 2: S3 audit bucket (encrypted, private, lifecycle) ############
resource "aws_s3_bucket" "audit" {
  bucket = "${var.project}-audit-${data.aws_caller_identity.me.account_id}"
}

resource "aws_s3_bucket_public_access_block" "audit" {
  bucket                  = aws_s3_bucket.audit.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "audit" {
  bucket = aws_s3_bucket.audit.id
  rule {
    id     = "archive-old-audit-records"
    status = "Enabled"
    filter {}
    transition {
      days          = 30
      storage_class = "GLACIER"
    }
    expiration {
      days = 365
    }
  }
}

############ MODULE 2: DynamoDB (one table: roll + sort key) ############
resource "aws_dynamodb_table" "portal" {
  name         = "${var.project}-data"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "roll"
  range_key    = "sk"

  attribute {
    name = "roll"
    type = "S"
  }
  attribute {
    name = "sk"
    type = "S"
  }
  server_side_encryption {
    enabled = true
  }
}

############ MODULE 4: IAM (least privilege) ############
resource "aws_iam_role" "lambda" {
  name = "${var.project}-lambda-role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy" "lambda" {
  name = "least-privilege"
  role = aws_iam_role.lambda.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["dynamodb:PutItem", "dynamodb:Query"], Resource = aws_dynamodb_table.portal.arn },
      { Effect = "Allow", Action = ["s3:PutObject"], Resource = "${aws_s3_bucket.audit.arn}/audit/*" },
      { Effect = "Allow", Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Resource = "arn:aws:logs:*:*:*" }
    ]
  })
}

############ MODULE 3: Serverless API (Lambda + API Gateway) ############
data "archive_file" "lambda" {
  type        = "zip"
  source_file = "${path.module}/../lambda/portal.py"
  output_path = "${path.module}/portal.zip"
}

resource "aws_lambda_function" "portal" {
  function_name    = "${var.project}-api"
  role             = aws_iam_role.lambda.arn
  handler          = "portal.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 10
  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.portal.name
      BUCKET     = aws_s3_bucket.audit.bucket
      ADMIN_KEY  = var.admin_key
    }
  }
}

resource "aws_apigatewayv2_api" "api" {
  name          = "${var.project}-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["GET", "POST", "OPTIONS"]
    allow_headers = ["content-type", "x-admin-key"]
  }
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.api.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.portal.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "routes" {
  for_each  = toset(["POST /attendance", "POST /results", "GET /students/{roll}"])
  api_id    = aws_apigatewayv2_api.api.id
  route_key = each.value
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
  default_route_settings {
    throttling_burst_limit = 20
    throttling_rate_limit  = 10
  }
}

resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.portal.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

############ MODULE 4: Monitoring and alerts ############
resource "aws_sns_topic" "alerts" {
  name = "${var.project}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "lambda_errors" {
  alarm_name          = "${var.project}-lambda-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.portal.function_name }
  statistic           = "Sum"
  period              = 60
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts.arn]
}

resource "aws_sns_topic" "billing" {
  provider = aws.virginia
  name     = "${var.project}-billing"
}

resource "aws_sns_topic_subscription" "billing_email" {
  provider  = aws.virginia
  topic_arn = aws_sns_topic.billing.arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "billing" {
  provider            = aws.virginia
  alarm_name          = "${var.project}-billing-alarm"
  namespace           = "AWS/Billing"
  metric_name         = "EstimatedCharges"
  dimensions          = { Currency = "USD" }
  statistic           = "Maximum"
  period              = 21600
  evaluation_periods  = 1
  threshold           = var.billing_threshold_usd
  comparison_operator = "GreaterThanThreshold"
  alarm_actions       = [aws_sns_topic.billing.arn]
}

resource "aws_cloudwatch_dashboard" "main" {
  dashboard_name = "${var.project}-dashboard"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "metric", x = 0, y = 0, width = 12, height = 6
        properties = {
          title   = "API Lambda invocations and errors"
          region  = var.region
          stat    = "Sum"
          period  = 60
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.portal.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.portal.function_name]
          ]
        }
      },
      {
        type = "metric", x = 12, y = 0, width = 12, height = 6
        properties = {
          title   = "DynamoDB writes"
          region  = var.region
          stat    = "Sum"
          period  = 60
          metrics = [["AWS/DynamoDB", "ConsumedWriteCapacityUnits", "TableName", aws_dynamodb_table.portal.name]]
        }
      }
    ]
  })
}

############ MODULE 1/2: Web server VM + firewall (default VPC) ############
data "aws_vpc" "default" {
  default = true
}

data "aws_ssm_parameter" "al2023" {
  name = "/aws/service/ami-amazon-linux-latest/al2023-ami-kernel-default-x86_64"
}

resource "aws_security_group" "web" {
  count       = var.create_vm ? 1 : 0
  name        = "${var.project}-web-sg"
  description = "HTTP from anywhere, SSH from my IP only"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip_cidr]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_instance" "web" {
  count                  = var.create_vm ? 1 : 0
  ami                    = data.aws_ssm_parameter.al2023.value
  instance_type          = "t3.micro"
  vpc_security_group_ids = [aws_security_group.web[0].id]
  user_data = templatefile("${path.module}/user_data.sh.tpl", {
    html = base64encode(replace(file("${path.module}/../frontend/index.html"), "__API_URL__", aws_apigatewayv2_api.api.api_endpoint))
  })
  root_block_device {
    encrypted = true
  }
  tags = { Name = "${var.project}-web" }
}
