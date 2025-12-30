output "lambda_function_arn" {
  description = "ARN of the Lambda function"
  value       = aws_lambda_function.rag_embedder_trigger.arn
}

output "api_gateway_endpoint" {
  description = "API Gateway endpoint URL"
  value       = aws_apigatewayv2_api.rag_embedder.api_endpoint
}

output "run_url" {
  description = "Full URL for the /run endpoint"
  value       = "${aws_apigatewayv2_api.rag_embedder.api_endpoint}/run"
}
