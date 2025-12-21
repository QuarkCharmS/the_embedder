output "zone_id" {
  description = "Route53 zone ID"
  value       = aws_route53_zone.internal.zone_id
}

output "zone_name" {
  description = "Route53 zone name"
  value       = aws_route53_zone.internal.name
}

output "name_servers" {
  description = "Route53 zone name servers"
  value       = aws_route53_zone.internal.name_servers
}
