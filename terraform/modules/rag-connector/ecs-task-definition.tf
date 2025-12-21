data "aws_caller_identity" "current" {}

resource "aws_ecs_task_definition" "rag_connector" {
  family                   = "rag-connector"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.cpu
  memory                   = var.memory
  execution_role_arn       = var.ecs_task_execution_role_arn

  container_definitions = jsonencode([
    {
      name  = "rag-connector"
      image = var.rag_connector_image

      portMappings = [
        {
          containerPort = 8000
          protocol      = "tcp"
        }
      ]

      secrets = [
        {
          name      = "QDRANT_HOST"
          valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-endpoint"
        },
        {
          name      = "QDRANT_PORT"
          valueFrom = "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-port"
        }
      ]

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/rag-connector"
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = merge(
    var.tags,
    {
      Name = "rag-connector"
    }
  )
}

resource "aws_cloudwatch_log_group" "rag_connector" {
  name              = "/ecs/rag-connector"
  retention_in_days = 7

  tags = merge(
    var.tags,
    {
      Name = "rag-connector-logs"
    }
  )
}
