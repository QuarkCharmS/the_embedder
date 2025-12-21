resource "aws_route53_record" "rag_connector" {
  zone_id = var.route53_zone_id
  name    = "rag-connector.internal"
  type    = "A"

  alias {
    name                   = data.aws_lb.nlb.dns_name
    zone_id                = data.aws_lb.nlb.zone_id
    evaluate_target_health = true
  }
}

data "aws_lb" "nlb" {
  arn = var.nlb_arn
}
