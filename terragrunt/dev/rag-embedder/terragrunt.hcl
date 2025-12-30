include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/rag-embedder"
}

dependencies {
  paths = ["../vpc", "../qdrant"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

dependency "qdrant" {
  config_path = "../qdrant"

  mock_outputs = {
    ecs_instances_security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

inputs = {
  aws_region  = "us-east-1"
  environment = "dev"

  vpc_id                     = dependency.vpc.outputs.vpc_id
  private_subnet_ids         = dependency.vpc.outputs.private_subnet_ids
  qdrant_security_group_id   = dependency.qdrant.outputs.ecs_instances_security_group_id

  rag_embedder_image = "418472915322.dkr.ecr.us-east-1.amazonaws.com/rag_embedder:v1.1"
  cpu                = 512
  memory             = 1024

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
