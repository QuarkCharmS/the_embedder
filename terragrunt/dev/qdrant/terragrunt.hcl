# Development environment Qdrant configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/qdrant"
}

# Declare dependencies for ordering
dependencies {
  paths = ["../vpc"]
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

inputs = {
  # Region and environment
  aws_region  = "us-east-1"
  environment = "dev"

  # Network (from VPC module)
  vpc_id             = dependency.vpc.outputs.vpc_id
  private_subnet_ids = dependency.vpc.outputs.private_subnet_ids
  public_subnet_ids  = dependency.vpc.outputs.public_subnet_ids

  # Compute resources (specify these for each deployment)
  instance_type   = "t3.large"
  ebs_volume_size = 20

  # Optional: Enable nip.io routing
  enable_nipio_routing = true
}
