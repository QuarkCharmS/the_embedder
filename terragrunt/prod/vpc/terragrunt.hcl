# Production environment VPC configuration
# Example: 3 AZs in eu-central-1

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/vpc"
}

inputs = {
  # Region - Deploy to EU for example
  aws_region = "eu-central-1"
  environment = "prod"

  vpc_cidr = "10.2.0.0/16"  # Different CIDR from dev/staging

  # 3 AZs for production high availability
  availability_zones = ["eu-central-1a", "eu-central-1b", "eu-central-1c"]

  # 3 subnets (one per AZ)
  public_subnet_cidrs  = ["10.2.1.0/24", "10.2.2.0/24", "10.2.3.0/24"]
  private_subnet_cidrs = ["10.2.11.0/24", "10.2.12.0/24", "10.2.13.0/24"]

  # NAT Gateway (💰 High availability - 3 NAT Gateways)
  enable_nat_gateway = true
  single_nat_gateway = false  # ~$96/month for 3 AZs
}
