output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.main.dns_name
}

output "alb_url" {
  description = "URL to access Qdrant via ALB"
  value       = "http://${aws_lb.main.dns_name}"
}

output "access_instructions" {
  description = "Instructions for accessing Qdrant"
  value       = <<-EOT
    Direct ALB access: http://${aws_lb.main.dns_name}

    To use nip.io (requires ALB IP):
    1. Get ALB IPs: dig ${aws_lb.main.dns_name}
    2. Use format: http://qdrant.<IP-with-dashes>.nip.io
       Example: http://qdrant.54-123-45-67.nip.io
  EOT
}

output "qdrant_node1_private_ip" {
  description = "Private IP of Qdrant node 1"
  value       = aws_instance.ecs_node1.private_ip
}

output "qdrant_node2_private_ip" {
  description = "Private IP of Qdrant node 2"
  value       = aws_instance.ecs_node2.private_ip
}

output "route53_zone_id" {
  description = "Route53 private hosted zone ID"
  value       = aws_route53_zone.private.zone_id
}

output "ecs_instances_security_group_id" {
  description = "Security group ID for ECS instances"
  value       = aws_security_group.ecs_instances.id
}
