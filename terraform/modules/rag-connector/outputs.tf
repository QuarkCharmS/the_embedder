output "service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.rag_connector.name
}

output "task_definition_arn" {
  description = "Task definition ARN"
  value       = aws_ecs_task_definition.rag_connector.arn
}

output "security_group_id" {
  description = "Security group ID for rag-connector tasks"
  value       = aws_security_group.rag_connector.id
}

output "internal_dns_name" {
  description = "Internal DNS name for rag-connector"
  value       = "rag-connector.internal"
}
