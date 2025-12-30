resource "aws_lambda_function" "rag_embedder_trigger" {
  filename         = "${var.lambda_source_dir}/lambda_function.zip"
  function_name    = "${var.environment}-rag-embedder-trigger"
  role             = aws_iam_role.lambda.arn
  handler          = "lambda_function.lambda_handler"
  source_code_hash = filebase64sha256("${var.lambda_source_dir}/lambda_function.zip")
  runtime          = "python3.12"
  timeout          = 30
  memory_size      = 256

  environment {
    variables = {
      TASK_DEFINITION_ARN = var.task_definition_arn
      ECS_CLUSTER         = var.ecs_cluster_name
      SUBNETS             = join(",", var.private_subnet_ids)
      SECURITY_GROUPS     = var.task_security_group_id
      CONTAINER_NAME      = "rag-embedder"
      ASSIGN_PUBLIC_IP    = "DISABLED"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic
  ]

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-rag-embedder-trigger"
    }
  )
}
