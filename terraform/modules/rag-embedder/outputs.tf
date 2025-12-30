output "task_definition_arn" {
  description = "ARN of the rag-embedder task definition"
  value       = aws_ecs_task_definition.rag_embedder.arn
}

output "task_role_arn" {
  description = "ARN of the task role"
  value       = aws_iam_role.task_role.arn
}

output "task_execution_role_arn" {
  description = "ARN of the task execution role"
  value       = aws_iam_role.task_execution.arn
}

output "security_group_id" {
  description = "Security group ID for rag-embedder tasks"
  value       = aws_security_group.rag_embedder.id
}
