variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs for ECS tasks"
  type        = list(string)
}

variable "ecs_cluster_id" {
  description = "ECS cluster ID"
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  type        = string
}

variable "nlb_arn" {
  description = "NLB ARN for internal access"
  type        = string
}

variable "alb_listener_arn" {
  description = "Shared ALB listener ARN for adding rules"
  type        = string
}

variable "alb_security_group_id" {
  description = "Shared ALB security group ID"
  type        = string
}

variable "route53_zone_id" {
  description = "Route53 internal zone ID"
  type        = string
}

variable "rag_connector_image" {
  description = "Docker image for rag-connector"
  type        = string
  default     = "418472915322.dkr.ecr.us-east-1.amazonaws.com/rag-connector:v1.1"
}

variable "enable_nipio_routing" {
  description = "Enable nip.io routing via ALB"
  type        = bool
  default     = true
}

variable "cpu" {
  description = "CPU units for Fargate task"
  type        = number
  default     = 256
}

variable "memory" {
  description = "Memory (MB) for Fargate task"
  type        = number
  default     = 512
}

variable "desired_count" {
  description = "Desired number of tasks"
  type        = number
  default     = 2
}

variable "tags" {
  description = "Additional tags to apply to resources"
  type        = map(string)
  default     = {}
}
