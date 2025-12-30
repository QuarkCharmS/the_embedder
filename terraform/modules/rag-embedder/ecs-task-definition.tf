data "aws_caller_identity" "current" {}

resource "aws_ecs_task_definition" "rag_embedder" {
  family                   = "rag-embedder"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([{
    name  = "rag-embedder"
    image = var.rag_embedder_image

    secrets = [
      {
        name      = "QDRANT_HOST"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-endpoint"
      },
      {
        name      = "QDRANT_PORT"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-port"
      },
      {
        name      = "GITHUB_TOKEN"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/github-token"
      },
      {
        name      = "API_TOKEN"
        valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/api-token"
      }
    ]

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/rag-embedder"
        "awslogs-region"        = var.aws_region
        "awslogs-stream-prefix" = "ecs"
      }
    }
  }])

  tags = merge(
    var.tags,
    {
      Name = "rag-embedder"
    }
  )
}

resource "aws_cloudwatch_log_group" "rag_embedder" {
  name              = "/ecs/rag-embedder"
  retention_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "rag-embedder-logs"
    }
  )
}
