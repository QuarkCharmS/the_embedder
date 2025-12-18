variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, prod)"
  type        = string
}

variable "ecs_cluster_id" {
  description = "ECS cluster ID from ECS module"
  type        = string
}

variable "ecs_cluster_name" {
  description = "ECS cluster name from ECS module"
  type        = string
}

variable "ecs_instance_profile_name" {
  description = "ECS instance IAM profile name from ECS module"
  type        = string
}

variable "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN from ECS module"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where Qdrant will be deployed"
  type        = string
}

variable "private_subnet_ids" {
  description = "Private subnet IDs (must be exactly 2, one per AZ)"
  type        = list(string)

  validation {
    condition     = length(var.private_subnet_ids) == 2
    error_message = "Exactly 2 private subnet IDs are required (one per AZ)"
  }
}

variable "public_subnet_ids" {
  description = "Public subnet IDs for ALB"
  type        = list(string)
}

variable "instance_type" {
  description = "EC2 instance type for ECS nodes"
  type        = string
}

variable "ebs_volume_size" {
  description = "Size of EBS volume for Qdrant data in GB"
  type        = number
}

variable "qdrant_image" {
  description = "Qdrant Docker image"
  type        = string
  default     = "qdrant/qdrant:v1.15.5"
}

variable "qdrant_memory" {
  description = "Memory per Qdrant container in MB"
  type        = number
  default     = 6144
}

variable "enable_nipio_routing" {
  description = "Enable nip.io routing for ALB"
  type        = bool
  default     = false
}
