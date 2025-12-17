# Development environment VPC configuration
# Can be deployed to any region by changing aws_region and availability_zones

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/vpc"
}

inputs = {
  # Region - Change this to deploy to different region
  aws_region = "us-east-1"

  # Environment tag
  environment = "dev"

  # VPC Configuration
  vpc_cidr = "10.0.0.0/16"

  # Availability Zones - Change based on region
  availability_zones = ["us-east-1a", "us-east-1b"]

  # Subnets - One per AZ
  public_subnet_cidrs  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnet_cidrs = ["10.0.11.0/24", "10.0.12.0/24"]

  # NAT Gateway (💰 Disabled for dev to save costs)
  enable_nat_gateway = false
  single_nat_gateway = false
}
