locals {
  default_region = "us-east-1"
}

remote_state {
  backend = "local"

  config = {
    path = "${get_terragrunt_dir()}/../state/${path_relative_to_include()}/terraform.tfstate"
  }
}

inputs = {
  aws_region = local.default_region
}
