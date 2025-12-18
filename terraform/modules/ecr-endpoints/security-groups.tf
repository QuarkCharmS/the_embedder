resource "aws_security_group" "vpc_endpoints" {
  name_prefix = "ecr-vpc-endpoints-"
  vpc_id      = var.vpc_id
  description = "Security group for ECR VPC endpoints"

  tags = merge(
    var.tags,
    {
      Name = "ecr-vpc-endpoints-sg"
    }
  )
}

# Allow HTTPS traffic from ECS instances to VPC endpoints
resource "aws_vpc_security_group_ingress_rule" "https_from_ecs" {
  count = length(var.allowed_security_group_ids)

  security_group_id            = aws_security_group.vpc_endpoints.id
  referenced_security_group_id = var.allowed_security_group_ids[count.index]
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  description                  = "Allow HTTPS from ECS instances"
}
