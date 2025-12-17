resource "aws_ecs_cluster" "main" {
  name = "qdrant-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "qdrant-cluster"
  }
}
