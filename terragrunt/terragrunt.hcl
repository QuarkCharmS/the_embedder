# Root Terragrunt configuration
# This file contains common settings for all environments

# Configure Terragrunt to use the S3 backend
remote_state {
  backend = "s3"

  config = {
    # S3 bucket for storing Terraform state
    bucket = "rag-system-tfstate"

    # Unique key per environment/region/module
    key = "${path_relative_to_include()}/terraform.tfstate"

    region         = "us-east-1"
    encrypt        = true

    # Optional: DynamoDB table for state locking
    # dynamodb_table = "terraform-locks"
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# Generate provider configuration
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<EOF
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      ManagedBy   = "terragrunt"
      Environment = var.environment
      Project     = "rag-system"
    }
  }
}
EOF
}

# Common inputs for all environments
inputs = {
  # These can be overridden in environment-specific configs
}
