output "nlb_id" {
  description = "NLB ID"
  value       = aws_lb.main.id
}

output "nlb_arn" {
  description = "NLB ARN"
  value       = aws_lb.main.arn
}

output "nlb_dns_name" {
  description = "NLB DNS name"
  value       = aws_lb.main.dns_name
}

output "nlb_zone_id" {
  description = "NLB zone ID"
  value       = aws_lb.main.zone_id
}
