# Staging environment VPC configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/vpc"
}

inputs = {
  # Region - Can be any AWS region
  aws_region = "us-east-1"
  environment = "staging"

  vpc_cidr = "10.1.0.0/16"  # Different CIDR from dev

  # Can use 2 or 3 AZs - just add more to the list
  availability_zones = ["us-east-1a", "us-east-1b"]

  public_subnet_cidrs  = ["10.1.1.0/24", "10.1.2.0/24"]
  private_subnet_cidrs = ["10.1.11.0/24", "10.1.12.0/24"]

  # NAT Gateway (💰 Single NAT for staging)
  enable_nat_gateway = true
  single_nat_gateway = true  # ~$32/month
}
