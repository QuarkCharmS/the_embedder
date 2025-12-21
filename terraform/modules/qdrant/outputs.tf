output "qdrant_node1_private_ip" {
  description = "Private IP of Qdrant node 1"
  value       = aws_instance.ecs_node1.private_ip
}

output "qdrant_node2_private_ip" {
  description = "Private IP of Qdrant node 2"
  value       = aws_instance.ecs_node2.private_ip
}

output "ecs_instances_security_group_id" {
  description = "Security group ID for ECS instances"
  value       = aws_security_group.ecs_instances.id
}

output "nlb_target_group_arn" {
  description = "NLB target group ARN"
  value       = aws_lb_target_group.qdrant_nlb.arn
}
