include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/route53-internal"
}

dependencies {
  paths = ["../vpc"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id = "vpc-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan", "destroy"]
}

inputs = {
  aws_region  = "us-east-1"
  environment = "dev"

  vpc_id = dependency.vpc.outputs.vpc_id

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
