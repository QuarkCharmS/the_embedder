include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/alb"
}

dependencies {
  paths = ["../vpc"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id            = "vpc-mock"
    public_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

inputs = {
  aws_region  = "us-east-1"
  environment = "dev"

  name              = "shared-alb"
  vpc_id            = dependency.vpc.outputs.vpc_id
  public_subnet_ids = dependency.vpc.outputs.public_subnet_ids

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
