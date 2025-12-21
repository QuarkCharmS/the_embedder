# Development environment Qdrant configuration

include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/qdrant"
}

# Declare dependencies for ordering
dependencies {
  paths = ["../vpc", "../ecs", "../alb", "../nlb", "../route53-internal", "../rag-connector"]
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

# Get ALB outputs
dependency "alb" {
  config_path = "../alb"

  mock_outputs = {
    alb_listener_arn      = "arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/app/mock/1234567890/1234567890"
    alb_security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Get Route53 internal zone outputs
dependency "route53_internal" {
  config_path = "../route53-internal"

  mock_outputs = {
    zone_id = "Z123456789MOCK"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Get NLB outputs
dependency "nlb" {
  config_path = "../nlb"

  mock_outputs = {
    nlb_arn      = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/net/mock/1234567890"
    nlb_dns_name = "mock-nlb.elb.us-east-1.amazonaws.com"
    nlb_zone_id  = "Z123456789MOCK"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

# Get RAG Connector outputs
dependency "rag_connector" {
  config_path = "../rag-connector"

  mock_outputs = {
    security_group_id = "sg-mock"
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

  # ALB (from shared ALB module)
  alb_listener_arn      = dependency.alb.outputs.alb_listener_arn
  alb_security_group_id = dependency.alb.outputs.alb_security_group_id

  # Route53 (from route53-internal module)
  route53_zone_id = dependency.route53_internal.outputs.zone_id

  # NLB (from nlb module)
  nlb_arn      = dependency.nlb.outputs.nlb_arn
  nlb_dns_name = dependency.nlb.outputs.nlb_dns_name
  nlb_zone_id  = dependency.nlb.outputs.nlb_zone_id

  # RAG Connector (from rag-connector module)
  rag_connector_security_group_id = dependency.rag_connector.outputs.security_group_id

  # Compute resources (specify these for each deployment)
  instance_type   = "t3.large"
  ebs_volume_size = 20

  # Optional: Enable nip.io routing
  enable_nipio_routing = true

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
