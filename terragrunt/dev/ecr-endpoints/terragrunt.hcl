# Development environment ECR VPC endpoints configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/ecr-endpoints"
}

# Declare dependencies for ordering
dependencies {
  paths = ["../vpc", "../qdrant", "../rag-connector", "../rag-embedder"]
}

# Get VPC outputs
dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id                  = "vpc-mock"
    private_subnet_ids      = ["subnet-mock-1", "subnet-mock-2"]
    private_route_table_ids = ["rtb-mock-1", "rtb-mock-2"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

# Get Qdrant outputs for ECS security group
dependency "qdrant" {
  config_path = "../qdrant"

  mock_outputs = {
    ecs_instances_security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

# Get rag-connector outputs for ECS task security group
dependency "rag_connector" {
  config_path = "../rag-connector"

  mock_outputs = {
    security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

# Get rag-embedder outputs for ECS task security group
dependency "rag_embedder" {
  config_path = "../rag-embedder"

  mock_outputs = {
    security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

inputs = {
  # Region and environment
  aws_region  = "us-east-1"
  environment = "dev"

  # VPC configuration
  vpc_id                     = dependency.vpc.outputs.vpc_id
  private_subnet_ids         = dependency.vpc.outputs.private_subnet_ids
  route_table_ids            = dependency.vpc.outputs.private_route_table_ids
  allowed_security_group_ids = [
    dependency.qdrant.outputs.ecs_instances_security_group_id,
    dependency.rag_connector.outputs.security_group_id,
    dependency.rag_embedder.outputs.security_group_id
  ]

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
