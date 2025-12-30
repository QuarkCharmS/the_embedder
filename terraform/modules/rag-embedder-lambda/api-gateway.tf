resource "aws_apigatewayv2_api" "rag_embedder" {
  name          = "${var.environment}-rag-embedder"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["content-type"]
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-rag-embedder-api"
    }
  )
}

resource "aws_apigatewayv2_integration" "lambda" {
  api_id                 = aws_apigatewayv2_api.rag_embedder.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.rag_embedder_trigger.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "run" {
  api_id    = aws_apigatewayv2_api.rag_embedder.id
  route_key = "POST /run"
  target    = "integrations/${aws_apigatewayv2_integration.lambda.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.rag_embedder.id
  name        = "$default"
  auto_deploy = true

  tags = merge(
    var.tags,
    {
      Name = "${var.environment}-rag-embedder-api-stage"
    }
  )
}

resource "aws_lambda_permission" "api_gateway" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.rag_embedder_trigger.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.rag_embedder.execution_arn}/*/*"
}
