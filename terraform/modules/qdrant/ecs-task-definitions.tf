resource "aws_ecs_task_definition" "node1" {
  family             = "qdrant-node1"
  network_mode       = "bridge"
  execution_role_arn = aws_iam_role.ecs_task_execution.arn

  volume {
    name      = "qdrant-data"
    host_path = "/mnt/qdrant-data"
  }

  container_definitions = jsonencode([{
    name      = "qdrant-node1"
    image     = var.qdrant_image
    essential = true
    memory    = 6144
    command   = ["./qdrant", "--uri", "http://qdrant1.qdrant.internal:6335"]

    environment = [{
      name  = "QDRANT__CLUSTER__ENABLED"
      value = "true"
    }]

    portMappings = [
      {
        containerPort = 6333
        hostPort      = 6333
        protocol      = "tcp"
      },
      {
        containerPort = 6335
        hostPort      = 6335
        protocol      = "tcp"
      }
    ]

    mountPoints = [{
      sourceVolume  = "qdrant-data"
      containerPath = "/qdrant/storage"
      readOnly      = false
    }]

    healthCheck = {
      command     = ["CMD-SHELL", "curl -f http://localhost:6333/ || exit 1"]
      interval    = 30
      timeout     = 5
      retries     = 3
      startPeriod = 60
    }

    logConfiguration = {
      logDriver = "awslogs"
      options = {
        "awslogs-group"         = "/ecs/qdrant-node1"
        "awslogs-region"        = var.aws_region
        "awslogs-create-group"  = "true"
        "awslogs-stream-prefix" = "qdrant"
      }
    }
  }])
}

resource "aws_ecs_task_definition" "node2" {
  family             = "qdrant-node2"
  network_mode       = "bridge"
  execution_role_arn = aws_iam_role.ecs_task_execution.arn

  volume {
    name      = "qdrant-data"
    host_path = "/mnt/qdrant-data"
  }

  container_definitions = jsonencode([
    {
      name      = "wait-for-node1"
      image     = "busybox:latest"
      essential = false
      memory    = 128
      command   = ["sh", "-c", "until nc -z qdrant1.qdrant.internal 6335; do echo 'Waiting for node1...'; sleep 5; done"]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/qdrant-node2"
          "awslogs-region"        = var.aws_region
          "awslogs-create-group"  = "true"
          "awslogs-stream-prefix" = "wait"
        }
      }
    },
    {
      name      = "qdrant-node2"
      image     = var.qdrant_image
      essential = true
      memory    = 6144
      command = [
        "./qdrant",
        "--bootstrap", "http://qdrant1.qdrant.internal:6335",
        "--uri", "http://qdrant2.qdrant.internal:6335"
      ]

      environment = [{
        name  = "QDRANT__CLUSTER__ENABLED"
        value = "true"
      }]

      dependsOn = [{
        containerName = "wait-for-node1"
        condition     = "SUCCESS"
      }]

      portMappings = [
        {
          containerPort = 6333
          hostPort      = 6333
          protocol      = "tcp"
        },
        {
          containerPort = 6335
          hostPort      = 6335
          protocol      = "tcp"
        }
      ]

      mountPoints = [{
        sourceVolume  = "qdrant-data"
        containerPath = "/qdrant/storage"
        readOnly      = false
      }]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = "/ecs/qdrant-node2"
          "awslogs-region"        = var.aws_region
          "awslogs-create-group"  = "true"
          "awslogs-stream-prefix" = "qdrant"
        }
      }
    }
  ])
}
