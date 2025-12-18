# Development environment ECS configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/ecs"
}

# Declare dependencies for ordering
dependencies {
  paths = ["../vpc"]
}

# Get VPC outputs
dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id = "vpc-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  cluster_name              = "qdrant-cluster"
  enable_container_insights = true

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
