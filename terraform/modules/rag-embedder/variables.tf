variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "private_subnet_ids" {
  type = list(string)
}

variable "qdrant_security_group_id" {
  type = string
}

variable "rag_embedder_image" {
  type    = string
  default = "418472915322.dkr.ecr.us-east-1.amazonaws.com/rag_embedder:v1.1"
}

variable "cpu" {
  type    = number
  default = 512
}

variable "memory" {
  type    = number
  default = 1024
}

variable "tags" {
  type    = map(string)
  default = {}
}
