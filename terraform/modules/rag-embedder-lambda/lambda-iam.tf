resource "aws_iam_role" "lambda" {
  name = "${var.environment}-rag-embedder-lambda"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_ecs" {
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecs:RunTask",
          "ecs:DescribeTaskDefinition"
        ]
        Resource = [
          var.task_definition_arn,
          replace(var.task_definition_arn, ":task-definition/", ":task-definition/rag-embedder:*")
        ]
      },
      {
        Effect = "Allow"
        Action = "ecs:TagResource"
        Resource = "arn:aws:ecs:*:*:task/*"
      },
      {
        Effect = "Allow"
        Action = "iam:PassRole"
        Resource = [
          var.task_role_arn,
          var.execution_role_arn
        ]
        Condition = {
          StringEquals = {
            "iam:PassedToService" = "ecs-tasks.amazonaws.com"
          }
        }
      }
    ]
  })
}
