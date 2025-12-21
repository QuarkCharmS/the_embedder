include "root" {
  path = find_in_parent_folders()
}

terraform {
  source = "../../../terraform/modules/rag-connector"
}

dependencies {
  paths = ["../vpc", "../ecs", "../nlb", "../alb", "../route53-internal"]
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    vpc_cidr           = "10.0.0.0/16"
    private_subnet_ids = ["subnet-mock-1", "subnet-mock-2"]
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "ecs" {
  config_path = "../ecs"

  mock_outputs = {
    cluster_id                  = "cluster-mock"
    cluster_name                = "cluster-mock"
    ecs_task_execution_role_arn = "arn:aws:iam::123456789012:role/mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "nlb" {
  config_path = "../nlb"

  mock_outputs = {
    nlb_arn = "arn:aws:elasticloadbalancing:us-east-1:123456789012:loadbalancer/net/mock/1234567890"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "alb" {
  config_path = "../alb"

  mock_outputs = {
    alb_listener_arn      = "arn:aws:elasticloadbalancing:us-east-1:123456789012:listener/app/mock/1234567890/1234567890"
    alb_security_group_id = "sg-mock"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

dependency "route53_internal" {
  config_path = "../route53-internal"

  mock_outputs = {
    zone_id = "Z123456789MOCK"
  }
  mock_outputs_allowed_terraform_commands = ["init", "validate", "plan"]
}

inputs = {
  aws_region  = "us-east-1"
  environment = "dev"

  vpc_id             = dependency.vpc.outputs.vpc_id
  vpc_cidr           = dependency.vpc.outputs.vpc_cidr
  private_subnet_ids = dependency.vpc.outputs.private_subnet_ids

  ecs_cluster_id              = dependency.ecs.outputs.cluster_id
  ecs_cluster_name            = dependency.ecs.outputs.cluster_name
  ecs_task_execution_role_arn = dependency.ecs.outputs.ecs_task_execution_role_arn

  nlb_arn               = dependency.nlb.outputs.nlb_arn
  alb_listener_arn      = dependency.alb.outputs.alb_listener_arn
  alb_security_group_id = dependency.alb.outputs.alb_security_group_id
  route53_zone_id       = dependency.route53_internal.outputs.zone_id

  enable_nipio_routing = true
  cpu                  = 256
  memory               = 512
  desired_count        = 2

  tags = {
    Environment = "dev"
    ManagedBy   = "terragrunt"
  }
}
