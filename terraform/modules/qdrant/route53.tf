resource "aws_route53_zone" "private" {
  name = "qdrant.internal"

  vpc {
    vpc_id = var.vpc_id
  }

  tags = {
    Name = "qdrant-private-zone"
  }
}

resource "aws_route53_record" "node1" {
  zone_id = aws_route53_zone.private.zone_id
  name    = "qdrant1.qdrant.internal"
  type    = "A"
  ttl     = 300
  records = [aws_instance.ecs_node1.private_ip]
}

resource "aws_route53_record" "node2" {
  zone_id = aws_route53_zone.private.zone_id
  name    = "qdrant2.qdrant.internal"
  type    = "A"
  ttl     = 300
  records = [aws_instance.ecs_node2.private_ip]
}
