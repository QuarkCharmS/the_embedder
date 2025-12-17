resource "aws_security_group" "alb" {
  name_prefix = "qdrant-alb-"
  vpc_id      = var.vpc_id
  description = "Security group for Qdrant ALB"

  tags = {
    Name = "qdrant-alb-sg"
  }
}

resource "aws_security_group" "ecs_instances" {
  name_prefix = "qdrant-ecs-"
  vpc_id      = var.vpc_id
  description = "Security group for Qdrant ECS instances"

  tags = {
    Name = "qdrant-ecs-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "alb_to_ecs" {
  security_group_id            = aws_security_group.alb.id
  referenced_security_group_id = aws_security_group.ecs_instances.id
  from_port                    = 6333
  to_port                      = 6333
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_from_alb" {
  security_group_id            = aws_security_group.ecs_instances.id
  referenced_security_group_id = aws_security_group.alb.id
  from_port                    = 6333
  to_port                      = 6333
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_cluster_6333" {
  security_group_id            = aws_security_group.ecs_instances.id
  referenced_security_group_id = aws_security_group.ecs_instances.id
  from_port                    = 6333
  to_port                      = 6333
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_ingress_rule" "ecs_cluster_6335" {
  security_group_id            = aws_security_group.ecs_instances.id
  referenced_security_group_id = aws_security_group.ecs_instances.id
  from_port                    = 6335
  to_port                      = 6335
  ip_protocol                  = "tcp"
}

resource "aws_vpc_security_group_egress_rule" "ecs_all" {
  security_group_id = aws_security_group.ecs_instances.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = "-1"
}
