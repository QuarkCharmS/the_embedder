resource "aws_route53_record" "node1" {
  zone_id = var.route53_zone_id
  name    = "qdrant1.qdrant"
  type    = "A"
  ttl     = 300
  records = [aws_instance.ecs_node1.private_ip]
}

resource "aws_route53_record" "node2" {
  zone_id = var.route53_zone_id
  name    = "qdrant2.qdrant"
  type    = "A"
  ttl     = 300
  records = [aws_instance.ecs_node2.private_ip]
}

resource "aws_route53_record" "qdrant" {
  zone_id = var.route53_zone_id
  name    = "qdrant"
  type    = "A"

  alias {
    name                   = var.nlb_dns_name
    zone_id                = var.nlb_zone_id
    evaluate_target_health = true
  }
}
