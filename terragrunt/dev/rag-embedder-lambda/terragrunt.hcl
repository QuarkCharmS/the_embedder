include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/rag-embedder-lambda"
}

dependencies {
  paths = ["../vpc", "../ecs", "../rag-embedder"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

dependency "ecs" {
  config_path = "../ecs"

  mock_outputs = {
    cluster_name = "qdrant-cluster"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

dependency "rag_embedder" {
  config_path = "../rag-embedder"

  mock_outputs = {
    task_definition_arn     = "arn:aws:ecs:us-east-1:123456789012:task-definition/rag-embedder:1"
    security_group_id       = "sg-mock"
    task_role_arn           = "arn:aws:iam::123456789012:role/mock-task-role"
    task_execution_role_arn = "arn:aws:iam::123456789012:role/mock-exec-role"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

inputs = {
  aws_region  = "us-east-1"
  environment = "dev"

  task_definition_arn    = dependency.rag_embedder.outputs.task_definition_arn
  ecs_cluster_name       = dependency.ecs.outputs.cluster_name
  private_subnet_ids     = dependency.vpc.outputs.private_subnet_ids
  task_security_group_id = dependency.rag_embedder.outputs.security_group_id
  task_role_arn          = dependency.rag_embedder.outputs.task_role_arn
  execution_role_arn     = dependency.rag_embedder.outputs.task_execution_role_arn
  lambda_source_dir      = "${get_repo_root()}/rag_embedder/lambda"

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
