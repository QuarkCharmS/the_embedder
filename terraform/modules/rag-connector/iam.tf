locals {
  ecs_task_execution_role_name = element(split("/", var.ecs_task_execution_role_arn), length(split("/", var.ecs_task_execution_role_arn)) - 1)
}

resource "aws_iam_role_policy" "ecr_pull" {
  name = "ecr-pull-rag-connector"
  role = local.ecs_task_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage"
        ]
        Resource = [
          "arn:aws:ecr:${var.aws_region}:418472915322:repository/rag-connector"
        ]
      }
    ]
  })
}

resource "aws_iam_role_policy" "ssm_parameters" {
  name = "ssm-parameters"
  role = local.ecs_task_execution_role_name

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ssm:GetParameters",
          "ssm:GetParameter"
        ]
        Resource = [
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-endpoint",
          "arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter/rag/dev/qdrant-port"
        ]
      },
      {
        Effect = "Allow"
        Action = ["kms:Decrypt"]
        Resource = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${var.aws_region}.amazonaws.com"
          }
        }
      }
    ]
  })
}
