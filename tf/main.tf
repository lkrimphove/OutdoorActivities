terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  default_tags {
    tags = {
      Service = "Outdoor Activities"
      Author  = "Lukas Krimphove"
    }
  }
}



data "http" "mime_types" {
  url = "https://gist.githubusercontent.com/lkrimphove/46988dc2ac63ad5ad9c95e6109e3c37e/raw/2349abeb136f1f8dbe91c661c928a5ce859432f9/mime.json"
  request_headers = {
    Accept = "application/json"
  }
}

locals {
  mime_types = jsondecode(data.http.mime_types.response_body)
}



### BUCKETS

module "input_bucket" {
  source = "terraform-aws-modules/s3-bucket/aws"

  bucket = var.input_bucket
  acl    = "private"

  control_object_ownership = true
  object_ownership         = "ObjectWriter"

}

module "output_bucket" {
  source = "terraform-aws-modules/s3-bucket/aws"

  bucket = var.output_bucket
  acl    = "private"

  control_object_ownership = true
  object_ownership         = "ObjectWriter"
}

resource "aws_s3_object" "object" {
  for_each     = fileset("../src/website", "*")
  bucket       = module.output_bucket.s3_bucket_id
  key          = each.value
  acl          = "private"
  source       = "../src/website/${each.value}"
  content_type = lookup(local.mime_types, split(".", each.value)[1], null)
  etag         = filemd5("../src/website/${each.value}")
}



### LAMBDA

module "lambda_function" {
  source = "terraform-aws-modules/lambda/aws"

  function_name = "outdoor-activities-generator"
  description   = "Generates a map containing your outdoor activities"
  handler       = "main.lambda_handler"
  runtime       = "python3.11"
  timeout       = 60

  source_path = "../src/lambda"

  environment_variables = {
    START_LATITUDE             = var.start_latitude
    START_LONGITUDE            = var.start_longitude
    ZOOM_START                 = var.zoom_start
    INPUT_BUCKET               = module.input_bucket.s3_bucket_id
    OUTPUT_BUCKET              = module.output_bucket.s3_bucket_id
    S3_OBJECT_NAME             = "map.html"
    CLOUDFRONT_DISTRIBUTION_ID = module.cloudfront.cloudfront_distribution_id
  }

  attach_policy = true
  policy        = aws_iam_policy.lambda_policy.arn
}

resource "aws_iam_policy" "lambda_policy" {
  name = "outdoor-activities-generator-policy"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = "s3:GetObject"
        Effect   = "Allow"
        Resource = "${module.input_bucket.s3_bucket_arn}/*"
      },
      {
        Action   = "s3:ListBucket"
        Effect   = "Allow"
        Resource = module.input_bucket.s3_bucket_arn
      },
      {
        Action   = "s3:PutObject"
        Effect   = "Allow"
        Resource = "${module.output_bucket.s3_bucket_arn}/*"
      },
      {
        Action   = "cloudfront:GetDistribution"
        Effect   = "Allow"
        Resource = module.cloudfront.cloudfront_distribution_arn
      },
      {
        Action   = "cloudfront:CreateInvalidation"
        Effect   = "Allow"
        Resource = module.cloudfront.cloudfront_distribution_arn
      }
    ]
  })
}

resource "aws_lambda_permission" "allow_bucket" {
  statement_id  = "AllowExecutionFromS3Bucket"
  action        = "lambda:InvokeFunction"
  function_name = module.lambda_function.lambda_function_arn
  principal     = "s3.amazonaws.com"
  source_arn    = module.input_bucket.s3_bucket_arn
}

resource "aws_s3_bucket_notification" "bucket_notification" {
  bucket = module.input_bucket.s3_bucket_id

  lambda_function {
    lambda_function_arn = module.lambda_function.lambda_function_arn
    events              = ["s3:ObjectCreated:*"]
  }

  depends_on = [aws_lambda_permission.allow_bucket]
}



### CLOUDFRONT

module "cloudfront" {
  source              = "terraform-aws-modules/cloudfront/aws"
  comment             = "Outdoor Activities Cloudfront"
  is_ipv6_enabled     = true
  price_class         = "PriceClass_100"
  wait_for_deployment = false

  create_origin_access_identity = true
  origin_access_identities = {
    s3_bucket = "s3_bucket_access"
  }

  origin = {
    s3_bucket = {
      domain_name = module.output_bucket.s3_bucket_bucket_regional_domain_name
      s3_origin_config = {
        origin_access_identity = "s3_bucket"
      }
    }
  }

  default_cache_behavior = {
    target_origin_id       = "s3_bucket"
    viewer_protocol_policy = "redirect-to-https"

    default_ttl = 5400
    min_ttl     = 3600
    max_ttl     = 7200

    allowed_methods = ["GET", "HEAD"]
    cached_methods  = ["GET", "HEAD"]
    compress        = true
    query_string    = false

    function_association = {
      viewer-request = {
        function_arn = aws_cloudfront_function.viewer_request.arn
      }
    }
  }

  default_root_object = "index.html"

  custom_error_response = [
    {
      error_code         = 403
      response_code      = 404
      response_page_path = "/404.html"
    },
    {
      error_code         = 404
      response_code      = 404
      response_page_path = "/404.html"
    }
  ]
}

data "aws_iam_policy_document" "s3_policy" {
  version = "2012-10-17"
  statement {
    actions   = ["s3:GetObject"]
    resources = ["${module.output_bucket.s3_bucket_arn}/*"]
    principals {
      type        = "AWS"
      identifiers = module.cloudfront.cloudfront_origin_access_identity_iam_arns
    }
  }
}

resource "aws_s3_bucket_policy" "docs" {
  bucket = module.output_bucket.s3_bucket_id
  policy = data.aws_iam_policy_document.s3_policy.json
}

resource "aws_cloudfront_function" "viewer_request" {
  name    = "cloudfront-viewer-request"
  runtime = "cloudfront-js-1.0"
  publish = true
  code    = file("../src/viewer-request.js")
}
