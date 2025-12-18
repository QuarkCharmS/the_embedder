# Development environment Qdrant configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/qdrant"
}

# Declare dependencies for ordering
dependencies {
  paths = ["../vpc", "../ecs"]
}

# Get VPC outputs
dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
    public_subnet_ids  = ["subnet-mock-3", "subnet-mock-4"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Get ECS outputs
dependency "ecs" {
  config_path = "../ecs"

  mock_outputs = {
    cluster_id                   = "cluster-mock"
    cluster_name                 = "qdrant-cluster"
    ecs_instance_profile_name    = "instance-profile-mock"
    ecs_task_execution_role_arn  = "arn:aws:iam::123456789012:role/mock-role"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  # Region and environment
  aws_region  = "us-east-1"
  environment = "dev"

  # Network (from VPC module)
  vpc_id             = dependency.vpc.outputs.vpc_id
  private_subnet_ids = dependency.vpc.outputs.private_subnet_ids
  public_subnet_ids  = dependency.vpc.outputs.public_subnet_ids

  # ECS (from ECS module)
  ecs_cluster_id               = dependency.ecs.outputs.cluster_id
  ecs_cluster_name             = dependency.ecs.outputs.cluster_name
  ecs_instance_profile_name    = dependency.ecs.outputs.ecs_instance_profile_name
  ecs_task_execution_role_arn  = dependency.ecs.outputs.ecs_task_execution_role_arn

  # Compute resources (specify these for each deployment)
  instance_type   = "t3.large"
  ebs_volume_size = 20

  # Optional: Enable nip.io routing
  enable_nipio_routing = true
}
