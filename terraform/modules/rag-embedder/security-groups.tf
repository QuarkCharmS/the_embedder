resource "aws_security_group" "rag_embedder" {
  name        = "${var.environment}-rag-embedder-task"
  description = "Security group for rag-embedder tasks"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.environment}-rag-embedder-task"
  }
}

resource "aws_vpc_security_group_egress_rule" "https" {
  security_group_id = aws_security_group.rag_embedder.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 443
  to_port           = 443
  ip_protocol       = "tcp"
  description       = "HTTPS for ECR, CloudWatch, APIs"
}

resource "aws_vpc_security_group_egress_rule" "http" {
  security_group_id = aws_security_group.rag_embedder.id
  cidr_ipv4         = "0.0.0.0/0"
  from_port         = 80
  to_port           = 80
  ip_protocol       = "tcp"
  description       = "HTTP for embedding APIs"
}

resource "aws_vpc_security_group_egress_rule" "qdrant" {
  security_group_id            = aws_security_group.rag_embedder.id
  referenced_security_group_id = var.qdrant_security_group_id
  from_port                    = 6333
  to_port                      = 6333
  ip_protocol                  = "tcp"
  description                  = "Qdrant access"
}
