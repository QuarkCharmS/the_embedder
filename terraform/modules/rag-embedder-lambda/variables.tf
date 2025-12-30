variable "aws_region" {
  type = string
}

variable "environment" {
  type = string
}

variable "task_definition_arn" {
  type = string
}

variable "ecs_cluster_name" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "task_security_group_id" {
  type = string
}

variable "task_role_arn" {
  type = string
}

variable "execution_role_arn" {
  type = string
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "lambda_source_dir" {
  type        = string
  description = "Path to the directory containing the Lambda function code"
}
