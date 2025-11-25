# Terraform configuration block
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# AWS provider configuration - Frankfurt region
provider "aws" {
  region = "eu-central-1"
}

# Create a new VPC with 10.0.0.0/16 CIDR
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "chunker-vpc"
  }
}

# Get ALL available zones in the region
data "aws_availability_zones" "available" {
  state = "available"
}

# Local values for calculations
locals {
  # List of all AZ names
  azs = data.aws_availability_zones.available.names
  
  # Calculate number of AZs
  az_count = length(local.azs)
}

# Frontend subnets - one per AZ
# Creates subnets: 10.0.1.0/24, 10.0.3.0/24, 10.0.5.0/24, etc.
resource "aws_subnet" "frontend" {
  count = local.az_count
  
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.${(count.index * 2) + 1}.0/24"  # 1, 3, 5, 7...
  availability_zone       = local.azs[count.index]
  map_public_ip_on_launch = true  # Frontend gets public IPs

  tags = {
    Name = "frontend-subnet-${local.azs[count.index]}"
    Type = "frontend"
    AZ   = local.azs[count.index]
  }
}

# Backend subnets - one per AZ  
# Creates subnets: 10.0.2.0/24, 10.0.4.0/24, 10.0.6.0/24, etc.
resource "aws_subnet" "backend" {
  count = local.az_count
  
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.${(count.index * 2) + 2}.0/24"  # 2, 4, 6, 8...
  availability_zone = local.azs[count.index]
  # No public IP for backend (more secure)

  tags = {
    Name = "backend-subnet-${local.azs[count.index]}"
    Type = "backend"
    AZ   = local.azs[count.index]
  }
}

# Internet Gateway (needed for frontend subnets to reach internet)
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "main-internet-gateway"
  }
}

# Route table for frontend subnets (public)
resource "aws_route_table" "frontend" {
  vpc_id = aws_vpc.main.id

  # Route to internet through IGW
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "frontend-route-table"
    Type = "public"
  }
}

# Route table for backend subnets (private)
resource "aws_route_table" "backend" {
  vpc_id = aws_vpc.main.id
  # No internet route - backend is private

  tags = {
    Name = "backend-route-table"
    Type = "private"
  }
}

# Associate ALL frontend subnets with frontend route table
resource "aws_route_table_association" "frontend" {
  count = local.az_count
  
  subnet_id      = aws_subnet.frontend[count.index].id
  route_table_id = aws_route_table.frontend.id
}

# Associate ALL backend subnets with backend route table
resource "aws_route_table_association" "backend" {
  count = local.az_count
  
  subnet_id      = aws_subnet.backend[count.index].id
  route_table_id = aws_route_table.backend.id
}


# S3 bucket configuration
resource "aws_s3_bucket" "rag_files" {
  bucket = "my-rag-files-bucket-${random_id.suffix.hex}" # ensures uniqueness
  
  tags = {
    Name        = "rag-files"
  }
}


# Optional: random suffix so the name is globally unique
resource "random_id" "suffix" {
  byte_length = 4
}


# S3 bucket outputs

output "s3_bucket_name" {
  value = aws_s3_bucket.rag_files.bucket
}

output "s3_bucket_arn" {
  value = aws_s3_bucket.rag_files.arn
}

output "s3_bucket_region" {
  value = aws_s3_bucket.rag_files.region
}

# Outputs to see what was created
output "vpc_id" {
  description = "ID of the VPC created"
  value       = aws_vpc.main.id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC created"
  value       = aws_vpc.main.cidr_block
}

output "availability_zones" {
  description = "All availability zones used"
  value       = local.azs
}

output "az_count" {
  description = "Number of availability zones"
  value       = local.az_count
}

output "frontend_subnets" {
  description = "All frontend subnet details"
  value = [
    for i in range(local.az_count) : {
      id   = aws_subnet.frontend[i].id
      cidr = aws_subnet.frontend[i].cidr_block
      az   = aws_subnet.frontend[i].availability_zone
      name = aws_subnet.frontend[i].tags.Name
    }
  ]
}

output "backend_subnets" {
  description = "All backend subnet details"  
  value = [
    for i in range(local.az_count) : {
      id   = aws_subnet.backend[i].id
      cidr = aws_subnet.backend[i].cidr_block
      az   = aws_subnet.backend[i].availability_zone
      name = aws_subnet.backend[i].tags.Name
    }
  ]
}

# Helper outputs for easy reference
output "frontend_subnet_ids" {
  description = "List of all frontend subnet IDs"
  value       = aws_subnet.frontend[*].id
}

output "backend_subnet_ids" {
  description = "List of all backend subnet IDs"
  value       = aws_subnet.backend[*].id
}
