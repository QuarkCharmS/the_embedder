module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"

  # VPC configuration (FREE) - Include environment in name
  name = "rag-${var.environment}-vpc"
  cidr = var.vpc_cidr

  # Subnets (FREE)
  azs             = var.availability_zones
  public_subnets  = var.public_subnet_cidrs
  private_subnets = var.private_subnet_cidrs

  # NAT Gateway (💰 COSTS MONEY: ~$32/month per NAT Gateway + ~$0.045/GB data processed)
  # Set to false to disable if you don't need private subnets to access the internet
  enable_nat_gateway = var.enable_nat_gateway

  # Single NAT Gateway (💰 $32/month for 1 NAT Gateway)
  # Set to false for high availability (💰 $64/month for 2 NAT Gateways, one per AZ)
  single_nat_gateway = var.single_nat_gateway

  # DNS settings (FREE)
  enable_dns_hostnames = true
  enable_dns_support   = true

  # Tags (FREE)
  tags = {
    Terraform = "true"
    Project   = "rag-system"
  }
}

# Cost Summary:
# - VPC: FREE
# - Subnets: FREE
# - Internet Gateway: FREE
# - Route Tables: FREE
# - NAT Gateway: 💰 ~$32/month (if enable_nat_gateway = true and single_nat_gateway = true)
#                💰 ~$64/month (if enable_nat_gateway = true and single_nat_gateway = false)
#                FREE (if enable_nat_gateway = false)
# - Data Transfer through NAT Gateway: 💰 ~$0.045 per GB
#
# Total estimated cost with default settings: ~$32-40/month
